# E-Hentai / ExHentai 本子預覽，翻頁跟 nhentai 一樣。
# 本子資料用官方 API（api.e-hentai.org 的 gdata），ExHentai 的本子也查得到，不用登入。
# 圖片要先開本子的縮圖頁拿到每頁的 imgkey，再開 /s/<imgkey>/<gid>-<頁> 才拿得到圖片網址（H@H 節點，帶時效簽章）；
# 有圖床時上傳到 Discord（舊訊息的圖不會過期），沒有圖床就直接用圖片網址。
# 圖片先找 e-hentai.org，只在 ExHentai 的本子（e-hentai 打不開）才用 token.json 的 exhentai_cookies 登入 exhentai.org。
# E-Hentai 開頁面太快會暫時封鎖 IP，所有頁面請求共用一個節流。
import asyncio
import html
import re
import time
from datetime import datetime, timezone

import aiohttp
import discord
from discord.ui import Button, View

import config
from utils.ttl_cache import async_ttl_cache
from functions.discord_cdn import LazySrc
from functions.cdn_pages import (apply_page, cdn_page_image, embed_thread_hint, strip_fragment,
                                 total_pages, current_page, JumpModal, reply_with_edit,
                                 message_lock, edit_attachments)

EHENTAI = {
    "name": "E-Hentai",
    "icon_url": "https://www.google.com/s2/favicons?domain=e-hentai.org&sz=128",
    "color": 0x5C0D12,
}
EXHENTAI = {
    "name": "ExHentai",
    # Google 抓不到 exhentai（沒登入是空白頁）會給地球圖示；兩站的 favicon 是同一張，借用 e-hentai 的
    "icon_url": "https://www.google.com/s2/favicons?domain=e-hentai.org&sz=128",
    "color": 0x34353B,
}
API = "https://api.e-hentai.org/api.php"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
}
GALLERY_URL = re.compile(r"(e-|ex)hentai\.org/g/(\d+)/([0-9a-f]{10})")
CATEGORIES = {
    "Doujinshi": "同人誌", "Manga": "漫畫", "Artist CG": "畫師 CG", "Game CG": "遊戲 CG", "Western": "歐美",
    "Non-H": "非 H", "Image Set": "圖集", "Cosplay": "Cosplay", "Asian Porn": "亞洲", "Misc": "其他",
}
LANGUAGES = {"chinese": "中文", "japanese": "日文", "english": "英文", "korean": "韓文", "speechless": "無對白"}
# 連線逾時、斷線之類的錯誤：當作這頁拿不到，不要讓整個預覽或翻頁失敗
_FETCH_ERRORS = (LookupError, aiohttp.ClientError, asyncio.TimeoutError)
# 兩次頁面請求的最小間隔（秒）
REQUEST_GAP = 0.25
_request_lock = None  # Python 3.9 的 Lock 建立時就綁定 event loop，等第一次請求才建立
_last_request = 0.0


def _cookies(host):
    # nw=1：略過部分本子的「Content Warning」確認頁
    return {"nw": "1", **(config.EXHENTAI_COOKIES if host == "exhentai.org" else {})}


def _hosts():
    return ["e-hentai.org", "exhentai.org"] if config.EXHENTAI_COOKIES else ["e-hentai.org"]


async def _get_html(session, url, host):
    global _request_lock, _last_request
    if _request_lock is None:
        _request_lock = asyncio.Lock()
    async with _request_lock:
        wait = _last_request + REQUEST_GAP - time.monotonic()
        if wait > 0:
            await asyncio.sleep(wait)
        _last_request = time.monotonic()
    # 沒登入開 exhentai 會被轉址到空白頁，不跟隨轉址
    async with session.get(url, headers=HEADERS, cookies=_cookies(host), allow_redirects=False,
                           timeout=aiohttp.ClientTimeout(total=15)) as resp:
        if resp.status != 200:
            raise LookupError(f"ehentai {url} -> {resp.status}")
        text = await resp.text()
    if "temporarily banned" in text:
        raise LookupError(f"ehentai IP banned: {text[:200]}")
    return text


COOKIE_NAMES = ("ipb_member_id", "ipb_pass_hash", "igneous")


def parse_cookie_text(text):
    """瀏覽器複製來的 Cookie 字串（"a=1; b=2"，或每行一個 name=value）取出登入用的三個值。"""
    pairs = (item.split("=", 1) for item in re.split(r"[;\n]", text) if "=" in item)
    found = {name.strip(): value.strip() for name, value in pairs}
    return {name: found[name] for name in COOKIE_NAMES if found.get(name)}


async def check_exhentai_cookies(session, cookies):
    """用這組 cookies 開 exhentai.org 首頁：登入失敗會回空白頁。成功回傳 cookies，
    沒給 igneous 時順便補上 exhentai 發的那個；失敗回傳 None。"""
    async with session.get("https://exhentai.org/", headers=HEADERS, cookies=cookies, allow_redirects=False,
                           timeout=aiohttp.ClientTimeout(total=15)) as resp:
        text = await resp.text()
        igneous = resp.cookies.get("igneous")
    if resp.status != 200 or len(text) < 1000:
        return None
    if "igneous" not in cookies and igneous is not None and igneous.value not in ("", "mystery"):
        cookies = {**cookies, "igneous": igneous.value}
    return cookies


async def _api(session, payload):
    async with session.post(API, json=payload, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=15)) as resp:
        if resp.status != 200:
            raise LookupError(f"ehentai api -> {resp.status}")
        return await resp.json(content_type=None)


@async_ttl_cache(ttl_seconds=1800, maxsize=256, key_arg="gid")
async def fetch_gdata(session, gid, token):
    data = await _api(session, {"method": "gdata", "gidlist": [[int(gid), token]], "namespace": 1})
    meta = (data.get("gmetadata") or [{}])[0]
    if "error" in meta or "title" not in meta:
        raise LookupError(f"ehentai gallery {gid}: {meta.get('error')}")
    return meta


async def resolve_page_link(session, imgkey, gid, page):
    """單頁連結 /s/<imgkey>/<gid>-<頁> 反查本子 token；找不到回傳 None。"""
    data = await _api(session, {"method": "gtoken", "pagelist": [[int(gid), imgkey, int(page)]]})
    tokens = data.get("tokenlist") or [{}]
    return tokens[0].get("token")


_PAGE_LINK = re.compile(r"(e-|ex)hentai\.org/s/([0-9a-f]{10})/(\d+)-(\d+)")
_GALLERY_LINK = re.compile(r"(e-|ex)hentai\.org/(?:g|mpv)/(\d+)/([0-9a-f]{10})")
_PLAIN_ID = re.compile(r"^\s*(\d+)[\s/]+([0-9a-f]{10})\s*$")
_GID_ONLY = re.compile(r"^\s*(\d+)\s*$")


@async_ttl_cache(ttl_seconds=86400, maxsize=512, key_arg="gid")
async def find_token(session, gid):
    """只有 gid 時找 token：列表頁 ?next=<gid+1> 從比它小的本子開始列，第一本就是它。
    已被刪除（不在列表上）的本子找不到；有 exhentai cookies 時再到 exhentai 找。回傳 (token, host)，找不到丟 LookupError。"""
    for host in _hosts():
        text = await _get_html(session, f"https://{host}/?next={int(gid) + 1}", host)
        first = re.search(rf"https://{re.escape(host)}/g/(\d+)/([0-9a-f]{{10}})", text)
        if first and first.group(1) == str(gid):
            return first.group(2), host
    raise LookupError(f"ehentai gid {gid} not listed")


async def parse_gallery_input(session, text):
    """斜線指令的輸入：本子網址、單頁網址、「gid token」或只有 gid。回傳 (gid, token, 頁碼或 None, 是否 ExHentai)；看不懂或找不到回傳 None。"""
    if match := _GALLERY_LINK.search(text):
        site, gid, token = match.groups()
        return gid, token, None, site == "ex"
    if match := _PAGE_LINK.search(text):
        site, imgkey, gid, page = match.groups()
        token = await resolve_page_link(session, imgkey, gid, page)
        return (gid, token, int(page), site == "ex") if token else None
    if match := _PLAIN_ID.match(text):
        return match.group(1), match.group(2), None, False
    if match := _GID_ONLY.match(text):
        try:
            token, host = await find_token(session, match.group(1))
        except _FETCH_ERRORS:
            return None
        return match.group(1), token, None, host == "exhentai.org"
    return None


def _parse_thumb_page(text, host, gid):
    keys = {int(n): key for key, n in re.findall(rf"https://{re.escape(host)}/s/([0-9a-f]{{10}})/{gid}-(\d+)", text)}
    total = re.search(r"Showing [\d,]+ - [\d,]+ of ([\d,]+) images", text)
    return keys, int(total.group(1).replace(",", "")) if total else None


@async_ttl_cache(ttl_seconds=1800, maxsize=256, key_arg="key")
async def _gallery_host(session, key):
    """找出能看這本圖的網站，回傳 (host, 第一個縮圖頁的 {頁碼: imgkey})。key = "<gid>/<token>"。"""
    gid, token = key.split("/")
    error = None
    for host in _hosts():
        try:
            text = await _get_html(session, f"https://{host}/g/{gid}/{token}/", host)
        except LookupError as e:
            error = e
            continue
        keys, _ = _parse_thumb_page(text, host, gid)
        if keys:  # 被移除、只在 ExHentai 上的本子這裡會是空的
            return host, keys
        if host == "exhentai.org" and len(text) < 1000:
            print("[ehentai] exhentai 回傳空白頁，exhentai_cookies 可能過期了，用 /excookies 更新")
    raise LookupError(f"ehentai gallery {key} has no viewable pages: {error!r}")


@async_ttl_cache(ttl_seconds=1800, maxsize=512, key_arg="key")
async def _thumb_page(session, key):
    """第 p 個縮圖頁（從 0 開始）的 {頁碼: imgkey}。key = "<gid>/<token>/<p>"。"""
    gid, token, p = key.split("/")
    host, first = await _gallery_host(session, f"{gid}/{token}")
    if p == "0":
        return first
    text = await _get_html(session, f"https://{host}/g/{gid}/{token}/?p={p}", host)
    return _parse_thumb_page(text, host, gid)[0]


async def _page_url(session, gid, token, page_num):
    """第 page_num 頁的瀏覽頁網址（/s/...）。"""
    host, first = await _gallery_host(session, f"{gid}/{token}")
    keys = first
    if page_num not in keys:
        per_page = len(first)  # 第一個縮圖頁就是 1..per_page
        keys = await _thumb_page(session, f"{gid}/{token}/{(page_num - 1) // per_page}")
    if page_num not in keys:
        raise LookupError(f"ehentai {gid} page {page_num} not found")
    return f"https://{host}/s/{keys[page_num]}/{gid}-{page_num}"


@async_ttl_cache(ttl_seconds=1200, maxsize=1024, key_arg="page_url")
async def _image_url(session, page_url):
    host = re.match(r"https://([^/]+)/", page_url).group(1)
    text = await _get_html(session, page_url, host)
    match = re.search(r'<img id="img" src="([^"]+)"', text)
    if not match:
        raise LookupError(f"ehentai {page_url} has no image")
    return html.unescape(match.group(1))


def ehentai_gallery(gid):
    return f"ehentai-{gid}"


async def ehentai_page_image(session, cdn, gid, token, page_num, total=None, thread_hint=None, inline=False):
    """第 page_num 頁：有圖床就是 Discord CDN 網址（並背景預載整本），否則是原站圖片網址；拿不到回傳 None。"""
    async def src_of(n):
        page_url = await _page_url(session, gid, token, n)
        return LazySrc(page_url, lambda: _image_url(session, page_url))

    try:
        url = await cdn_page_image(cdn, ehentai_gallery(gid), page_num, src_of, total,
                                   thread_hint=thread_hint, inline=inline)
        return url or await _image_url(session, await src_of(int(page_num)))
    except _FETCH_ERRORS as e:
        print(f"[ehentai] {gid} page {page_num} failed: {e!r}")
        return None


def _tag_groups(tags):
    groups = {}
    for tag in tags or []:
        namespace, _, name = html.unescape(tag).rpartition(":")
        groups.setdefault(namespace or "misc", []).append(name)
    return groups


async def ehentai_embed(session, gid, token, page_num=1, cdn=None, ex=False):
    """回傳 (embed, 頁數)；頁數 > 1 時呼叫端附上 EHentaiView 翻頁。找不到本子回傳 (None, 0)。"""
    try:
        meta = await fetch_gdata(session, gid, token)
    except _FETCH_ERRORS as e:
        print(f"[ehentai] gallery {gid} failed: {e!r}")
        return None, 0
    site = EXHENTAI if ex else EHENTAI
    url = f"https://{'exhentai' if ex else 'e-hentai'}.org/g/{gid}/{token}/"
    title, title_jpn = html.unescape(meta.get("title") or ""), html.unescape(meta.get("title_jpn") or "")
    embed = discord.Embed(title=(title_jpn or title or str(gid))[:256], url=url, color=site["color"])
    embed.set_author(name=site["name"], url=url.split("/g/")[0] + "/", icon_url=site["icon_url"])
    if title_jpn and title:
        embed.description = title[:350]

    tags = _tag_groups(meta.get("tags"))
    artists = tags.get("artist", []) + tags.get("group", [])
    if artists:
        embed.add_field(name="作者", value="、".join(artists)[:1024])
    if tags.get("parody"):
        embed.add_field(name="原作", value="、".join(tags["parody"])[:1024])
    if tags.get("character"):
        embed.add_field(name="角色", value="、".join(tags["character"])[:1024])
    embed.add_field(name="分類", value=CATEGORIES.get(meta.get("category"), meta.get("category") or "-"))
    languages = [LANGUAGES.get(l, l) for l in tags.get("language", []) if l not in ("translated", "rewrite")]
    if languages:
        embed.add_field(name="語言", value="、".join(languages))
    if meta.get("rating"):
        embed.add_field(name="評分", value=f"⭐ {meta['rating']}")
    marked = [("♀" if ns == "female" else "♂" if ns == "male" else "") + t
              for ns in ("female", "male", "mixed", "other", "misc") for t in tags.get(ns, [])]
    if marked:
        embed.add_field(name="標籤", value=", ".join(marked)[:1024], inline=False)
    if meta.get("uploader"):
        embed.add_field(name="上傳者", value=html.unescape(meta["uploader"]))
    if meta.get("expunged"):
        embed.add_field(name="狀態", value="已被刪除")
    if str(meta.get("posted") or "").isdigit():
        embed.timestamp = datetime.fromtimestamp(int(meta["posted"]), tz=timezone.utc)

    pages = int(meta.get("filecount") or 0)
    img = None
    if pages:
        embed.add_field(name="頁數", value=str(pages))
        page_num = max(1, min(int(page_num), pages))
        img = await ehentai_page_image(session, cdn, gid, token, page_num, pages, inline=True)
    if img:
        apply_page(embed, img, page_num, cdn, ehentai_gallery(gid), colour=site["color"])
    else:
        # 開不了圖（例如只在 ExHentai 上、又沒設定 cookies）就只放封面縮圖，不翻頁
        if meta.get("thumb"):
            embed.set_image(url=meta["thumb"])
        pages = 0
    return embed, pages


async def render_ehentai_page(session, cdn, embed: discord.Embed, target):
    """翻頁、跳頁共用：只換圖片與頁碼。回傳實際的頁碼；拿不到圖時頁面不變。"""
    _, gid, token = GALLERY_URL.search(strip_fragment(embed.url)).groups()
    total = total_pages(embed)
    target = max(1, min(int(target), total)) if total else max(1, int(target))
    img = await ehentai_page_image(session, cdn, gid, token, target, total,
                                   thread_hint=embed_thread_hint(embed), inline=True)
    if not img:
        return current_page(embed)
    apply_page(embed, img, target, cdn, ehentai_gallery(gid))
    return target


class EHentaiView(View):
    def __init__(self, session: aiohttp.ClientSession = None, embed: discord.Embed = None):
        super().__init__(timeout=None)
        self.session = session
        # 舊訊息共用 persistent View，每次操作都從該訊息讀取頁碼
        if embed is not None:
            self.middle_button.label = f"{current_page(embed)}/{total_pages(embed)}"

    async def _render(self, interaction: discord.Interaction, embed: discord.Embed, target):
        cdn = getattr(interaction.client, "image_cdn", None)
        target = await render_ehentai_page(self.session or interaction.client.session, cdn, embed, target)
        self.middle_button.label = f"{target}/{total_pages(embed)}"
        return dict(embed=embed, view=self, attachments=edit_attachments(embed))

    async def _go(self, interaction: discord.Interaction, target_of):
        embed = interaction.message.embeds[0]

        async def work():
            async with message_lock(interaction.message.id):
                return await self._render(interaction, embed, target_of(current_page(embed), total_pages(embed)))

        await reply_with_edit(interaction, work)

    @discord.ui.button(label='<<', style=discord.ButtonStyle.gray, custom_id="ehentai:first")
    async def decreasetostart(self, interaction: discord.Interaction, button: Button):
        await self._go(interaction, lambda current, total: 1)

    @discord.ui.button(label='<', style=discord.ButtonStyle.gray, custom_id="ehentai:prev")
    async def decrease(self, interaction: discord.Interaction, button: Button):
        await self._go(interaction, lambda current, total: max(1, current - 1))

    @discord.ui.button(label="-", style=discord.ButtonStyle.primary, custom_id="ehentai:jump")
    async def middle_button(self, interaction: discord.Interaction, button: Button):
        """中間按鈕：開啟跳頁視窗。"""
        total = total_pages(interaction.message.embeds[0])

        async def on_jump(modal_interaction, target):
            embed = modal_interaction.message.embeds[0]

            async def work():
                async with message_lock(modal_interaction.message.id):
                    return await self._render(modal_interaction, embed, target)

            await reply_with_edit(modal_interaction, work)

        await interaction.response.send_modal(JumpModal(total, on_jump))

    @discord.ui.button(label='>', style=discord.ButtonStyle.gray, custom_id="ehentai:next")
    async def increase(self, interaction: discord.Interaction, button: Button):
        await self._go(interaction, lambda current, total: min(total or current + 1, current + 1))

    @discord.ui.button(label='>>', style=discord.ButtonStyle.gray, custom_id="ehentai:last")
    async def increasetoend(self, interaction: discord.Interaction, button: Button):
        await self._go(interaction, lambda current, total: total or current)
