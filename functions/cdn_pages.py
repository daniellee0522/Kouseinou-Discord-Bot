"""wnacg / nhentai / 禁漫 翻頁共用的圖床流程與 embed 工具。

每本對應圖床上的一個討論串（gallery 名稱例如 wnacg-317161、nhentai-680635、jm-622529），
第 n 頁的 key 是 f"{gallery}-{n}"。embed 上記錄：
- footer：目前頁碼
- embed.url 的 #cdn=<討論串 ID>：重啟後靠它找回這本的索引，不需要本地存檔
"""
import asyncio
import io
import re
import time

import discord

from functions.discord_cdn import thread_id_from_url

CDN_FRAGMENT = re.compile(r"#cdn=(\d+)")
# 曾短暫把 embed 改成按鈕的藍紫色；翻頁時把這種 embed 換回各站原本的顏色
_MISTAKEN_COLOR = 0x5865F2
CDN_PAGE = re.compile(r"-(\d+)\.\w+(?:\?|$)")
# 整本都排過預載的相簿，這段時間內翻頁不再重新排
PREFETCH_DONE_TTL = 1800
_prefetch_done = {}
_prefetch_running = set()
# 第一次送出時直接附在回覆訊息上的圖：id(embed) -> discord.File
_pending_files = {}


class InlineImage(str):
    """attachment://<檔名>：第一頁直接附在回覆訊息上（只要一次 API 呼叫），
    同時在背景傳進討論串建立索引。file 是要跟著訊息一起送出的附件。"""

    def __new__(cls, filename, file):
        obj = super().__new__(cls, f"attachment://{filename}")
        obj.file = file
        return obj


def cdn_files(embed: discord.Embed):
    """送出 embed 時要一起附上的檔案（send(..., **cdn_files(embed))）。"""
    file = _pending_files.pop(id(embed), None)
    return {"files": [file]} if file is not None else {}


def edit_attachments(embed: discord.Embed):
    """翻頁編輯訊息時的附件：這頁直接附圖就換上它，否則清掉先前附在訊息上的圖。"""
    file = _pending_files.pop(id(embed), None)
    return [file] if file is not None else []


# 每則訊息各自一把鎖：重開機後所有舊訊息共用 on_ready 註冊的同一個 View 實例，
# 若用 View 上的鎖，一則訊息現場上傳時會卡住所有人的翻頁
_message_locks = {}


def message_lock(message_id):
    lock = _message_locks.get(message_id)
    if lock is None:
        if len(_message_locks) > 1000:
            for mid in [m for m, l in _message_locks.items() if not l.locked()]:
                del _message_locks[mid]
        lock = _message_locks[message_id] = asyncio.Lock()
    return lock


def page_key(gallery, page_num):
    return f"{gallery}-{int(page_num)}"


def embed_thread_hint(embed: discord.Embed):
    """embed 上記錄的圖床討論串 ID：放在 embed.url 的 #cdn=...，
    沒有的話從圖片網址（cdn.discordapp.com/attachments/<討論串>/...）推回來。"""
    match = CDN_FRAGMENT.search(embed.url or "")
    if match:
        return int(match.group(1))
    image_url = embed.image.url if embed.image else None
    return thread_id_from_url(image_url)


def strip_fragment(url):
    return CDN_FRAGMENT.sub("", url or "")


def apply_page(embed: discord.Embed, img, page_num, cdn=None, gallery=None, colour=None):
    """把某一頁套到 embed 上：圖片、footer 頁碼，以及 embed.url 的圖床討論串 ID。
    舊版 embed 翻頁時也會經過這裡，順便升級成帶索引的新格式。"""
    embed.set_image(url=img)
    embed.set_footer(text=str(page_num))
    if embed.colour is not None and embed.colour.value == _MISTAKEN_COLOR:
        embed.colour = colour
    thread_id = cdn.thread_of(gallery) if cdn is not None and cdn.enabled and gallery else None
    if isinstance(img, InlineImage):
        _pending_files[id(embed)] = img.file
        # 圖片網址會在使用者的頻道，不能拿來推討論串；還不知道討論串時記 0，之後翻頁再補上
        thread_id = thread_id or 0
    if thread_id is not None and embed.url:
        embed.url = strip_fragment(embed.url) + f"#cdn={thread_id}"


def current_page(embed: discord.Embed, legacy=None):
    """目前頁碼：footer → 圖床檔名（xxx-<頁>.jpg）→ 各站舊格式 legacy(image_url)。"""
    footer = getattr(embed, "footer", None)
    text = footer.text if footer else None
    if text and text.isdigit():
        return int(text)
    image = getattr(embed, "image", None)
    image_url = image.url if image else None
    if image_url and "cdn.discordapp.com" in image_url:
        match = CDN_PAGE.search(image_url)
        if match:
            return int(match.group(1))
    if legacy is not None and image_url:
        return legacy(image_url)
    return 1


def total_pages(embed: discord.Embed):
    for item in embed.fields:
        if item.name == "頁數" and str(item.value).strip().isdigit():
            return int(str(item.value).strip())
    return None


async def _resolve(value):
    if callable(value):
        value = value()
    if asyncio.iscoroutine(value):
        value = await value
    return value


async def _prefetch(cdn, gallery, start, total, src_of, transform_for):
    if gallery in _prefetch_running:
        return
    _prefetch_running.add(gallery)
    try:
        total = await _resolve(total)
        if not total:
            return
        order = list(range(start + 1, total + 1)) + list(range(start, 0, -1))
        items = [(page_key(gallery, n), await src_of(n), transform_for(n) if transform_for else None)
                 for n in order]
        cdn.prefetch(gallery, items, priority=1)
        _prefetch_done[gallery] = time.monotonic() + PREFETCH_DONE_TTL
    except Exception as e:
        print(f"[cdn] prefetch {gallery} failed: {e!r}", flush=True)
    finally:
        _prefetch_running.discard(gallery)


# 跳到還沒上傳的頁時，接下來幾頁立刻插隊預載，不必等整本依序傳到這裡
JUMP_WINDOW = 3


async def _prefetch_window(cdn, gallery, page_num, total, src_of, transform_for):
    try:
        total = await _resolve(total)
        if not total:
            return
        items = []
        for n in range(page_num + 1, min(total, page_num + JUMP_WINDOW) + 1):
            if not cdn.cached(page_key(gallery, n)):
                items.append((page_key(gallery, n), await src_of(n), transform_for(n) if transform_for else None))
        if items:
            cdn.prefetch(gallery, items, priority=0)
    except Exception as e:
        print(f"[cdn] prefetch window {gallery} failed: {e!r}", flush=True)


def schedule_prefetch(cdn, gallery, start, total, src_of, transform_for=None):
    """背景把整本上傳到圖床：從目前頁往後優先，再補前面的頁。"""
    if cdn is None or not cdn.enabled or total is None:
        return
    if _prefetch_done.get(gallery, 0) > time.monotonic():
        return
    asyncio.create_task(_prefetch(cdn, gallery, int(start), total, src_of, transform_for))


async def cdn_page_image(cdn, gallery, page_num, src_of, total=None, transform_for=None, thread_hint=None,
                         inline=False):
    """回傳第 page_num 頁的 Discord CDN 網址；沒設定圖床或上傳失敗回傳 None（呼叫端退回原本網址）。
    索引有就直接用（不碰來源站），沒有就立刻上傳這一頁；並在背景預載整本，
    之後翻頁、跳頁都直接命中索引。
    src_of: async (頁碼) -> 原圖網址；total: 總頁數（數字或 async 函式），None 表示不預載；
    transform_for: (頁碼) -> transform(bytes) -> (bytes, 副檔名)，例如 JM 每頁不同的切片還原。"""
    if cdn is None or not cdn.enabled:
        return None
    page_num = int(page_num)
    cdn.remember_thread(gallery, thread_hint)
    key = page_key(gallery, page_num)
    url = await cdn.lookup(gallery, key, wait_scan=not inline)
    if not url:
        transform = transform_for(page_num) if transform_for else None
        try:
            src = await src_of(page_num)
            if inline:
                # 圖直接附在回覆／編輯的訊息上（一次 API 呼叫），不等上傳到討論串；
                # 這頁本身一定排進討論串建立索引（沿用已下載的資料），再預載附近與整本
                data, ext = await cdn.fetch(src, transform)
                cdn.preload(key, data, ext)
                cdn.prefetch(gallery, [(key, src, transform)], priority=0)
                if total is not None:
                    asyncio.create_task(_prefetch_window(cdn, gallery, page_num, total, src_of, transform_for))
                schedule_prefetch(cdn, gallery, page_num, total, src_of, transform_for)
                return InlineImage(key + ext, discord.File(io.BytesIO(data), filename=key + ext))
        except Exception as e:
            print(f"[cdn] {key} source failed: {e!r}", flush=True)
            return None
        url = await cdn.ensure(gallery, key, src, transform)
        if url and total is not None:
            asyncio.create_task(_prefetch_window(cdn, gallery, page_num, total, src_of, transform_for))
    if url:
        schedule_prefetch(cdn, gallery, page_num, total, src_of, transform_for)
    return url


# 互動要在 3 秒內回應；這段時間內頁面備妥就直接用一次 edit_message 回應（省一次 API 呼叫），
# 來不及（例如要現場上傳）才先 defer 再編輯訊息
FAST_REPLY = 2.0


async def run_within_deadline(interaction: discord.Interaction, work, ephemeral=False):
    """執行 work()。FAST_REPLY 內完成回傳 (結果, False)：呼叫端直接用 interaction.response 回應；
    來不及就先 defer，等完回傳 (結果, True)：呼叫端改用 followup / message.edit。"""
    task = asyncio.ensure_future(work())
    try:
        return await asyncio.wait_for(asyncio.shield(task), FAST_REPLY), False
    except asyncio.TimeoutError:
        await interaction.response.defer(ephemeral=ephemeral)
        return await task, True


async def reply_with_edit(interaction: discord.Interaction, work):
    """翻頁、跳頁共用的回應方式。work() 回傳 message.edit 的參數。"""
    kwargs, deferred = await run_within_deadline(interaction, work)
    if deferred:
        await interaction.message.edit(**kwargs)
    else:
        await interaction.response.edit_message(**kwargs)


async def reply_with_send(interaction: discord.Interaction, work):
    """斜線指令共用：work() 回傳 send 的參數；來得及就一次 send_message 回覆，否則 defer 後 followup。"""
    kwargs, deferred = await run_within_deadline(interaction, work)
    if deferred:
        await interaction.followup.send(**kwargs)
    else:
        await interaction.response.send_message(**kwargs)


class JumpModal(discord.ui.Modal, title="跳轉頁數"):
    """中間按鈕開的跳頁視窗；on_jump(interaction, 頁碼) 由各站的 View 提供。"""
    page_input = discord.ui.TextInput(label="輸入要跳轉的頁數", placeholder="例如：5",
                                      style=discord.TextStyle.short, required=True, max_length=5)

    def __init__(self, total, on_jump):
        super().__init__()
        self.total = total
        self.on_jump = on_jump
        if total:
            self.page_input.label = f"輸入要跳轉的頁數（1-{total}）"

    async def on_submit(self, interaction: discord.Interaction):
        try:
            target = int(self.page_input.value)
        except ValueError:
            return await interaction.response.send_message("請輸入合法的整數頁數。", ephemeral=True)
        if target < 1 or (self.total and target > self.total):
            return await interaction.response.send_message(f"頁數需介於 1 到 {self.total} 之間。", ephemeral=True)
        await self.on_jump(interaction, target)
