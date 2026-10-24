"""把外部圖片上傳到 Discord 圖床頻道，embed 直接用 cdn.discordapp.com 網址。

不做本地存檔，索引全部放在 Discord 上：
- 每一本（gallery，例如 wnacg-317161）一個討論串，圖片附件檔名就是 key（wnacg-317161-3.jpg）。
- embed 上記錄討論串 ID（由呼叫端放在 embed.url 的 #cdn=...），重啟後讀一次該討論串
  的歷史訊息就能重建這本的索引；沒有記錄時，啟動時掃描頻道的討論串名稱找回來。
- 記憶體索引只是快取：附件網址的 ex 簽章約 24 小時過期，過期就重讀討論串換新簽章。

上傳分兩種：
- ensure()：使用者正在等的那頁（貼連結、翻頁、跳頁），直接下載上傳，不排隊。
- prefetch()：背景把整本預先上傳，同一本最多 10 張打包成一則訊息。
同一個 key 同時只會有一個上傳；正在上傳中的 key 會等它完成，不會重複上傳。
"""
import asyncio
import io
import itertools
import os
import re
import time
from urllib.parse import urlparse, parse_qs

import aiohttp
import discord

try:
    import httpx  # HTTP/2：同一主機的多個下載共用一條連線
except ImportError:  # pragma: no cover
    httpx = None

MAX_FILES_PER_MESSAGE = 10
# bot 單則訊息附件總大小上限約 10MB，留一點餘裕
MAX_MESSAGE_BYTES = 9 * 1024 * 1024
# 簽章到期前多久就視為過期，避免剛送出去就失效
EXPIRY_MARGIN = 600
SCAN_WAIT = 10
DOWNLOAD_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.61 Safari/537.36"
}
ATTACHMENT_URL = re.compile(r"cdn\.discordapp\.com/attachments/(\d+)/")


class HeaderSrc(str):
    """下載時要帶額外標頭的圖片網址（例如 hitomi 一定要 Referer，不然回 404）。"""

    def __new__(cls, url, headers):
        obj = super().__new__(cls, url)
        obj.headers = headers
        return obj


class LazySrc(str):
    """下載前才解析真正網址的圖片來源（例如 E-Hentai 每頁的圖要先開該頁才知道）。
    字串本身只是識別用的頁面網址；resolve() 回傳實際要下載的網址（可以是 HeaderSrc）。
    預載整本時排隊很便宜，真的輪到下載才去開頁面。"""

    def __new__(cls, page_url, resolve):
        obj = super().__new__(cls, page_url)
        obj.resolve = resolve
        return obj


def url_expiry(url):
    """讀取附件網址 ex 參數（16 進位 unix 時間）；沒有的話回傳 None。"""
    try:
        return int(parse_qs(urlparse(url).query)["ex"][0], 16)
    except (KeyError, ValueError, IndexError):
        return None


def is_fresh(url):
    ex = url_expiry(url)
    return ex is None or ex - EXPIRY_MARGIN > time.time()


def thread_id_from_url(url):
    """從圖床附件網址取出所在的討論串（頻道）ID。"""
    match = ATTACHMENT_URL.search(url or "")
    return int(match.group(1)) if match else None


def _extension(src):
    ext = os.path.splitext(urlparse(src).path)[1].lower()
    return ext if ext in (".jpg", ".jpeg", ".png", ".gif", ".webp") else ".jpg"


def _normalize(item):
    key, src, *rest = item
    return key, src, (rest[0] if rest else None)


def _group_by_size(prepared):
    group, size = [], 0
    for name, data in prepared:
        if group and (len(group) >= MAX_FILES_PER_MESSAGE or size + len(data) > MAX_MESSAGE_BYTES):
            yield group
            group, size = [], 0
        group.append((name, data))
        size += len(data)
    if group:
        yield group


def _shrink(data):
    """超過單則上限的圖重新壓成 JPEG，逐步降低品質直到放得下。"""
    from PIL import Image
    image = Image.open(io.BytesIO(data)).convert("RGB")
    for quality in (85, 75, 65, 50):
        out = io.BytesIO()
        image.save(out, "JPEG", quality=quality)
        if out.tell() <= MAX_MESSAGE_BYTES:
            break
    return out.getvalue(), ".jpg"


class DiscordImageCDN:
    def __init__(self, bot, channel_id, prefetch_workers=2, use_http2=True):
        self.bot = bot
        # 圖片來源多在海外（nhentai 一次來回約 0.3 秒）：新連線光 TCP+TLS 就要約 0.9 秒，
        # 加上 TCP 慢啟動，一張圖要 2 秒；沿用已建立的連線只要 0.3 秒。所以下載走共用的
        # HTTP/2 連線（並行請求也在同一條連線上），沒裝 httpx 時退回 aiohttp。
        self._use_http2 = use_http2 and httpx is not None
        self._http = None
        self.channel_id = int(channel_id or 0)
        self.prefetch_workers = prefetch_workers
        self._urls = {}            # key -> 附件網址（記憶體快取）
        self._threads = {}         # gallery -> 討論串 ID
        self._loaded = {}          # 討論串 ID -> 讀取歷史的時間
        self._futures = {}         # key -> Future[url]，上傳中的 key
        self._gallery_locks = {}
        self._load_locks = {}
        self._jobs = None
        self._channel = None
        self._preloaded = {}       # key -> (bytes, 副檔名)：已經下載處理好、等著傳進討論串的圖
        self._job_seq = itertools.count()
        self._scan_done = asyncio.Event()

    @property
    def enabled(self):
        return self.channel_id != 0

    # ---------- 啟動 ----------
    def start(self):
        """bot ready 後呼叫：背景掃描既有討論串並啟動預載 worker。"""
        if not self.enabled or self._jobs is not None:
            return
        # 優先序佇列：0 = 使用者剛看的頁與接下來幾頁，1 = 整本背景預載（切成每 10 張一批，
        # 不會長時間占住 worker，讓別人翻頁要的頁可以插隊）
        self._jobs = asyncio.PriorityQueue()
        for _ in range(self.prefetch_workers):
            asyncio.create_task(self._prefetch_worker())
        asyncio.create_task(self._scan_threads())

    async def _scan_threads(self):
        try:
            channel = await self._get_channel(self.channel_id)
            for thread in channel.threads:
                self._threads.setdefault(thread.name, thread.id)
            async for thread in channel.archived_threads(limit=None):
                self._threads.setdefault(thread.name, thread.id)
            print(f"[cdn] scanned {len(self._threads)} threads", flush=True)
        except Exception as e:
            print(f"[cdn] thread scan failed: {e!r}", flush=True)
        finally:
            self._scan_done.set()

    # ---------- 索引 ----------
    def thread_of(self, gallery):
        return self._threads.get(gallery)

    def remember_thread(self, gallery, thread_id):
        """呼叫端從 embed 上讀到的討論串 ID。"""
        if thread_id:
            self._threads[gallery] = int(thread_id)

    def cached(self, key):
        url = self._urls.get(key)
        return url if url and is_fresh(url) else None

    async def _find_thread(self, gallery, wait_scan=True):
        self.start()
        thread_id = self._threads.get(gallery)
        if thread_id is None and wait_scan and not self._scan_done.is_set():
            try:
                await asyncio.wait_for(self._scan_done.wait(), SCAN_WAIT)
            except asyncio.TimeoutError:
                pass
            thread_id = self._threads.get(gallery)
        return thread_id

    async def _load_thread(self, thread_id, force=False):
        """讀取討論串所有附件，重建該本的 key -> 網址。"""
        lock = self._load_locks.setdefault(thread_id, asyncio.Lock())
        async with lock:
            if not force and thread_id in self._loaded:
                return
            try:
                async for message in self._thread(thread_id).history(limit=None, oldest_first=True):
                    for attachment in message.attachments:
                        key = os.path.splitext(attachment.filename)[0]
                        self._urls[key] = attachment.url
                self._loaded[thread_id] = time.time()
            except discord.HTTPException as e:
                print(f"[cdn] load thread {thread_id} failed: {e!r}", flush=True)

    async def lookup(self, gallery, key, wait_scan=True):
        """查索引（必要時讀討論串歷史）；找不到回傳 None，不會上傳。
        wait_scan=False：啟動掃描還沒完成時不等它（呼叫端找不到也能直接附圖回應）。"""
        url = self.cached(key)
        if url:
            return url
        self.start()
        thread_id = await self._find_thread(gallery, wait_scan)
        if thread_id is None:
            return None
        # 沒讀過就讀；讀過但網址過期就重讀換新簽章
        await self._load_thread(thread_id, force=key in self._urls)
        return self.cached(key)

    # ---------- 對外介面 ----------
    async def ensure(self, gallery, key, src, transform=None):
        """回傳 key 的 CDN 網址；還沒上傳就立刻上傳並等待結果。失敗回傳 None。
        transform(bytes) -> (bytes, 副檔名) 會在上傳前於執行緒中處理（例如 JM 的切片還原）。"""
        try:
            url = await self.lookup(gallery, key)
            if url:
                return url
            fut = self._futures.get(key)
            if fut is None:
                await self._upload(gallery, [(key, src, transform)])
                return self.cached(key)
            return await asyncio.shield(fut)
        except Exception as e:
            print(f"[cdn] {key} upload failed: {e!r}", flush=True)
            return None

    def prefetch(self, gallery, items, priority=1):
        """背景預先上傳 [(key, src) 或 (key, src, transform), ...]；
        已存在或上傳中的會在處理時跳過。priority 0 優先於 1。"""
        if not self.enabled:
            return
        self.start()
        items = [_normalize(item) for item in items]
        for i in range(0, len(items), MAX_FILES_PER_MESSAGE):
            self._jobs.put_nowait((priority, next(self._job_seq), gallery, items[i:i + MAX_FILES_PER_MESSAGE]))

    async def _prefetch_worker(self):
        while True:
            _, _, gallery, items = await self._jobs.get()
            try:
                await self.lookup(gallery, items[0][0])  # 先讀討論串歷史，已上傳的就不重傳
                chunk = []
                for item in items:
                    if self.cached(item[0]):
                        self._preloaded.pop(item[0], None)
                    elif item[0] not in self._futures:
                        chunk.append(item)
                if chunk:
                    await self._upload(gallery, chunk)
            except Exception as e:
                print(f"[cdn] prefetch {gallery} failed: {e!r}", flush=True)

    # ---------- 上傳 ----------
    async def fetch(self, src, transform=None):
        """下載並處理一張圖（transform、過大時壓縮），回傳 (bytes, 副檔名)。"""
        if isinstance(src, LazySrc):
            src = await src.resolve()
        data = await self._download(src)
        if transform is not None:
            data, ext = await asyncio.to_thread(transform, data)
        else:
            ext = _extension(src[0] if isinstance(src, (list, tuple)) else src)
        if len(data) > MAX_MESSAGE_BYTES:
            data, ext = await asyncio.to_thread(_shrink, data)
        return data, ext

    def preload(self, key, data, ext):
        """已經下載好的圖（例如直接附在回覆訊息上的第一頁），之後傳進討論串時不必再下載。"""
        self._preloaded[key] = (data, ext)

    async def _prepare(self, src, transform, key=None):
        if key in self._preloaded:
            return self._preloaded.pop(key)
        return await self.fetch(src, transform)

    async def _upload(self, gallery, items):
        items = [_normalize(item) for item in items]
        loop = asyncio.get_running_loop()
        for key, _, _ in items:
            self._futures[key] = loop.create_future()
        try:
            results = await asyncio.gather(*(self._prepare(src, tf, key) for key, src, tf in items),
                                           return_exceptions=True)
            prepared = []
            for (key, _, _), result in zip(items, results):
                if isinstance(result, Exception):
                    self._futures[key].set_exception(result)
                    continue
                data, ext = result
                prepared.append((key + ext, data))
            # 單則訊息有大小上限，大圖（例如 nhentai 原圖）依總大小分批送
            for group in _group_by_size(prepared):
                files = [discord.File(io.BytesIO(data), filename=name) for name, data in group]
                message = await self._send(gallery, files)
                for attachment in message.attachments:
                    key = os.path.splitext(attachment.filename)[0]
                    self._urls[key] = attachment.url
                    self._preloaded.pop(key, None)  # 別的批次已經傳了這頁，預先下載的資料就不用留
                    fut = self._futures.get(key)
                    if fut is not None and not fut.done():
                        fut.set_result(attachment.url)
        except Exception as e:
            for key, _, _ in items:
                fut = self._futures.get(key)
                if fut is not None and not fut.done():
                    fut.set_exception(e)
            raise
        finally:
            for key, _, _ in items:
                fut = self._futures.pop(key, None)
                if fut is not None and not fut.done():
                    fut.set_exception(RuntimeError("upload produced no attachment"))
                if fut is not None and not fut.cancelled():
                    fut.exception()  # 沒人等的失敗不要印 "never retrieved" 警告

    async def _send(self, gallery, files):
        """傳到該本的討論串；還沒有討論串就建立（論壇頻道建串時順便附上圖片）。"""
        lock = self._gallery_locks.setdefault(gallery, asyncio.Lock())
        async with lock:
            thread_id = await self._find_thread(gallery)
            if thread_id is None and not self._scan_done.is_set():
                # 開新串前一定等啟動掃描完成，避免舊本子被當成新的而重開一串、整本重傳
                # （這裡只在背景上傳時執行，不影響回應速度）
                await self._scan_done.wait()
                thread_id = self._threads.get(gallery)
            if thread_id is None:
                channel = await self._get_channel(self.channel_id)
                if isinstance(channel, discord.ForumChannel):
                    created = await channel.create_thread(name=gallery, files=files)
                    thread, message = created.thread, created.message
                else:
                    thread = await channel.create_thread(
                        name=gallery, type=discord.ChannelType.public_thread,
                        # 1 小時沒動靜就封存，活躍討論串數量維持很低，不會撞到伺服器 1000 串上限；
                        # 之後往封存的串上傳會自動解除封存
                        auto_archive_duration=60)
                    message = await thread.send(files=files)
                self._threads[gallery] = thread.id
                self._loaded.setdefault(thread.id, time.time())
                return message
        return await self._thread(thread_id).send(files=files)

    def _client(self):
        if self._http is None:
            self._http = httpx.AsyncClient(
                http2=True, headers=DOWNLOAD_HEADERS, timeout=30, follow_redirects=True,
                limits=httpx.Limits(max_connections=50, keepalive_expiry=300))
        return self._http

    async def _download(self, src):
        """src 可以是多個網址：依序嘗試，前一個失敗才換下一個（同主機才能沿用熱連線，不同時開多條）。"""
        if isinstance(src, (list, tuple)):
            error = None
            for url in src:
                try:
                    return await self._download(url)
                except Exception as e:
                    error = e
            raise error
        extra = getattr(src, "headers", None)
        if self._use_http2:
            resp = await self._client().get(src, headers=extra)
            resp.raise_for_status()
            return resp.content
        async with self.bot.session.get(src, headers={**DOWNLOAD_HEADERS, **(extra or {})},
                                        timeout=aiohttp.ClientTimeout(total=30)) as resp:
            resp.raise_for_status()
            return await resp.read()

    def warm(self, url):
        """背景先對圖片主機建立連線（例如爬 nhentai 頁面的同時），之後取圖省掉 TCP+TLS 的時間。"""
        if not self.enabled or not self._use_http2:
            return

        async def _warm():
            try:
                await self._client().get(url)
            except Exception:
                pass

        asyncio.create_task(_warm())

    async def close(self):
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    def _thread(self, thread_id):
        """只憑 ID 就能讀歷史、送訊息；不必先 fetch_channel（封存的討論串不在快取裡，會多一次 API 呼叫）。"""
        return self.bot.get_partial_messageable(thread_id)

    async def _get_channel(self, channel_id):
        if channel_id == self.channel_id and self._channel is not None:
            return self._channel
        channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
        if channel_id == self.channel_id:
            self._channel = channel
        return channel
