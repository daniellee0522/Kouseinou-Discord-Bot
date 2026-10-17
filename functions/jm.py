import asyncio
from bs4 import BeautifulSoup
import discord
from curl_cffi import requests
from discord.ui import Button, View
import re
import io
import sys
import hashlib
import time

sys.path.append(r"./")
import config
from functions.cdn_pages import (apply_page, cdn_page_image, embed_thread_hint, schedule_prefetch,
                                 strip_fragment, total_pages, JumpModal, reply_with_edit,
                                 message_lock, edit_attachments)

sys.stdout = io.TextIOWrapper(
    sys.stdout.buffer, encoding='utf-8')



FLARESOLVERR_URL = "http://localhost:8191/v1"

_DIRECT_HEADERS = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,'
              'application/signed-exchange;v=b3;q=0.7',
    'accept-language': 'zh-TW,zh;q=0.9',
}


def _parse_jm_page(html, url):
    """解析頁面 HTML，取不到頁數（通常代表被 Cloudflare 擋下）時回傳 None。"""
    soup = BeautifulSoup(html, 'lxml')

    title = soup.title.text if soup.title else ""
    try:
        title = title[:title.index("|")]
    except ValueError:
        pass

    album_id = extract_number_from_url(url)
    if album_id is None:
        pattern = re.compile(r'/album/(\d+)/')
        for script in soup.find_all("script"):
            if script.string:
                match = pattern.search(script.string)
                if match:
                    album_id = match.group(1)
                    break

    pagecount_span = soup.find("span", class_="pagecount")
    if not pagecount_span:
        return None
    page_count = int(re.search(r"\d+", pagecount_span.get_text()).group())

    return title, page_count, album_id, _parse_jm_meta(soup)


def _parse_jm_meta(soup):
    """作品／登場人物／標籤／作者：頁面上同一組區塊會出現兩次（手機/桌面版），只取第一次出現的。"""
    meta = {}
    for span in soup.select("span[data-type]"):
        key = span.get("data-type")
        if key in meta:
            continue
        names = []
        for a in span.find_all("a"):
            name = a.get_text(strip=True)
            if name and name not in names:
                names.append(name)
        meta[key] = names
    return meta


# (data-type, 欄位名稱, 最多顯示幾個)；順序跟 nhentai / wnacg 一致：作者、標籤…最後才是頁數
JM_META_FIELDS = [
    ("author", "作者", 10),
    ("tags", "標籤", 30),
    ("works", "作品", 5),
    ("actor", "登場人物", 10),
]


def _meta_value(names, limit):
    value = "、".join(names[:limit])
    if len(names) > limit:
        value += f" …等 {len(names)} 個"
    # Discord 欄位上限 1024 字
    return value if len(value) <= 1024 else value[:1021] + "..."


def jm_crawl(url):
    # 先用有偽裝 TLS 指紋的直接請求，速度快、多數時候就能過 Cloudflare
    try:
        request = requests.get(url, headers=_DIRECT_HEADERS, impersonate="chrome124", timeout=15)
        result = _parse_jm_page(request.text, url)
        if result:
            return result
    except Exception:
        pass

    # Cloudflare 加強阻擋時，直接請求會被擋下(沒有 pagecount 或直接失敗)，
    # 改交給本機的 FlareSolverr（會開無頭瀏覽器真的解 JS challenge）再試一次
    payload = {
        "cmd": "request.get",
        "url": url,
        "maxTimeout": 60000,
    }
    response = requests.post(FLARESOLVERR_URL, json=payload, timeout=65).json()
    if response.get("status") != "ok":
        raise RuntimeError(f"FlareSolverr 解析失敗：{response.get('message')}")
    html = response["solution"]["response"]

    result = _parse_jm_page(html, url)
    if not result:
        raise RuntimeError("JM 頁面解析失敗（FlareSolverr 也無法取得頁數資訊），可能是頁面結構已變更")
    return result


# 同一本 30 分鐘內重貼不再重爬（只快取成功結果）
JM_CRAWL_TTL = 1800
_jm_crawl_cache = {}


def jm_crawl_cached(url):
    key = extract_number_from_url(url) or url
    cached = _jm_crawl_cache.get(key)
    if cached and cached[0] > time.monotonic():
        return cached[1]
    result = jm_crawl(url)
    if len(_jm_crawl_cache) > 256:
        _jm_crawl_cache.clear()
    _jm_crawl_cache[key] = (time.monotonic() + JM_CRAWL_TTL, result)
    return result


def jm_embed(url):
    id = extract_number_from_url(url)
    if id == None:
        title, page, id, meta = jm_crawl_cached(url)
    else:
        title, page, _, meta = jm_crawl_cached(url)

    # 網址裡沒有相簿 ID 時改用標準網址，翻頁按鈕才讀得到 ID
    if extract_number_from_url(url) is None:
        url = f"https://18comic.vip/album/{id}/"
    embed = discord.Embed(title=title, url=url, color=JM_COLOR)
    embed.set_author(
        name="禁漫天堂", icon_url="https://i.imgur.com/dYVERFN.png")
    for key, name, limit in JM_META_FIELDS:
        names = meta.get(key)
        if names:
            embed.add_field(name=name, value=_meta_value(names, limit))
    embed.add_field(name="頁數", value=page)
    embed.set_thumbnail(url=f"{config.PIC_PROXY_URL}/transform?url=https://cdn-msp3.18comic.org/media/albums/{id}.jpg")
    url3 = f"https://cdn-msp.18comic.org/media/photos/{id}/00001.webp"

    # 該處裡的清單

    embed.set_image(url=f"{config.PIC_PROXY_URL}/transform?url={url3}")

    return embed

# ---------- 圖床 ----------
# 原圖網域：cdn-msp.18comic.org 憑證有問題，跟 host 的 REDIRECT_MAP 一樣改走 18comic.vip
JM_IMAGE_HOST = "https://18comic.vip"
JM_COLOR = 0xe37e31


def jm_gallery(album_id):
    return f"jm-{album_id}"


def jm_source(album_id, page_num):
    return f"{JM_IMAGE_HOST}/media/photos/{album_id}/{fillnum(page_num)}.webp"


def jm_legacy_url(album_id, page_num):
    """沒有圖床時沿用的 host 轉換網址。"""
    return f"{config.PIC_PROXY_URL}/transform?url=https://cdn-msp.18comic.org/media/photos/{album_id}/{fillnum(page_num)}.webp"


def jm_pieces(album_id, page):
    """圖片被切成幾條（對應 host.py 的 get_num）：依相簿 ID 與頁碼字串（00001）的 md5 決定。"""
    e = int(album_id)
    if e <= 220971:
        return 1
    if e >= 268850:
        n = ord(hashlib.md5(f"{album_id}{page}".encode()).hexdigest()[-1])
        n %= 8 if e >= 421926 else 10
        return [2, 4, 6, 8, 10, 12, 14, 16, 18, 20][n]
    return 10


def jm_descramble(album_id, page, data):
    """還原禁漫的切條打亂（對應 host.py 的 convertImg）：由上往下切成 piece 條，
    最後一條包含除不盡的餘數，再整個上下反序拼回去。輸出 WEBP。"""
    from PIL import Image
    image = Image.open(io.BytesIO(data))
    image.load()
    image = image.convert("RGB")
    piece = jm_pieces(album_id, page)
    if piece > 1:
        width, height = image.size
        block = height // piece
        strips = []
        for i in range(piece):
            top = i * block
            bottom = height if i == piece - 1 else top + block
            strips.append(image.crop((0, top, width, bottom)))
        restored = Image.new("RGB", (width, height))
        y = 0
        for strip in reversed(strips):
            restored.paste(strip, (0, y))
            y += strip.size[1]
        image = restored
    # WEBP（method=0 最快）比 JPEG 小約 35%，上傳較快；編碼約 0.02 秒
    out = io.BytesIO()
    image.save(out, "WEBP", quality=80, method=0)
    return out.getvalue(), ".webp"


def jm_transform_for(album_id):
    return lambda n: (lambda data: jm_descramble(album_id, fillnum(n), data))


async def jm_page_image(cdn, album_id, page_num, total=None, thread_hint=None, inline=False):
    """第 page_num 頁的圖片網址：有圖床就是還原後的 Discord CDN 網址，否則沿用 host 轉換網址。
    total 有值時背景預載整本。"""
    async def src_of(n):
        return jm_source(album_id, n)

    url = await cdn_page_image(cdn, jm_gallery(album_id), page_num, src_of, total,
                               transform_for=jm_transform_for(album_id), thread_hint=thread_hint,
                               inline=inline)
    return url or jm_legacy_url(album_id, page_num)


def jm_schedule_prefetch(cdn, album_id, start, total):
    async def src_of(n):
        return jm_source(album_id, n)
    schedule_prefetch(cdn, jm_gallery(album_id), start, total, src_of, jm_transform_for(album_id))


async def jm_embed_async(url, cdn=None):
    """建立禁漫 embed：爬頁面（較慢）與第一頁上傳圖床同時進行，送出時已是 CDN 網址。"""
    album_id = extract_number_from_url(url)
    image_task = asyncio.create_task(jm_page_image(cdn, album_id, 1, inline=True)) if album_id else None
    try:
        embed = await asyncio.to_thread(jm_embed, url)
    except Exception:
        if image_task:
            image_task.cancel()
        raise
    if album_id is None:
        album_id = extract_number_from_url(embed.url)
    img = await image_task if image_task else await jm_page_image(cdn, album_id, 1, inline=True)
    apply_page(embed, img, 1, cdn, jm_gallery(album_id), colour=JM_COLOR)
    total = total_pages(embed)
    if total:
        jm_schedule_prefetch(cdn, album_id, 1, total)
    return embed


def extract_page_number(url: str) -> int:
    from urllib.parse import unquote
    url_decoded = unquote(url)
    match = re.search(r'/(\d{5})\.webp', url_decoded)
    if match:
        return int(match.group(1))
    return 1


def extract_number_from_url(url):
    pattern = r'/(\d+)(?:/|$)'

    match = re.search(pattern, url)

    if match:
        return int(match.group(1))
    else:
        return None


def fillnum(num):
    num = str(num)
    while len(num) < 5:
        num = "0" + num

    return num


class NumberView3(discord.ui.View):
    def __init__(self, embed: discord.Embed = None):
        super().__init__(timeout=None)
        self.number = 1
        # 舊訊息共用 persistent View，每次操作都從該訊息讀取頁碼。
        if embed is not None:
            self._sync_number(embed)
            self.middle_button.label = f"{self.number}/{total_pages(embed)}"

    def _sync_number(self, embed: discord.Embed):
        """頁碼：footer（新版）→ 舊版 host 轉換網址裡的 /00001.webp。"""
        footer = getattr(embed, "footer", None)
        if footer and footer.text and footer.text.isdigit():
            self.number = int(footer.text)
            return
        self.number = extract_page_number(embed.image.url)

    async def _render(self, interaction: discord.Interaction, embed: discord.Embed, target):
        """翻頁、跳頁共用；舊版 embed（host 轉換網址）會在這裡升級成圖床格式。"""
        cdn = getattr(interaction.client, "image_cdn", None)
        album_id = extract_number_from_url(strip_fragment(embed.url))
        total = total_pages(embed)
        target = max(1, min(int(target), total)) if total else max(1, int(target))
        img = await jm_page_image(cdn, album_id, target, total=total, thread_hint=embed_thread_hint(embed),
                                  inline=True)
        apply_page(embed, img, target, cdn, jm_gallery(album_id), colour=JM_COLOR)
        self.number = target
        self.middle_button.label = f"{target}/{total}"
        return dict(embed=embed, view=self, attachments=edit_attachments(embed))

    async def _go(self, interaction: discord.Interaction, target_of):
        embed = interaction.message.embeds[0]

        async def work():
            async with message_lock(interaction.message.id):
                self._sync_number(embed)
                return await self._render(interaction, embed, target_of(self.number, total_pages(embed)))

        await reply_with_edit(interaction, work)

    @discord.ui.button(label='<<', style=discord.ButtonStyle.gray, custom_id="21")
    async def decreasetostart(self, interaction: discord.Interaction, button: Button):
        await self._go(interaction, lambda current, total: 1)

    @discord.ui.button(label='<', style=discord.ButtonStyle.gray, custom_id="22")
    async def decrease(self, interaction: discord.Interaction, button: Button):
        await self._go(interaction, lambda current, total: max(1, current - 1))

    @discord.ui.button(label="-", style=discord.ButtonStyle.primary, custom_id="23")
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

    @discord.ui.button(label='>', style=discord.ButtonStyle.gray, custom_id="24")
    async def increase(self, interaction: discord.Interaction, button: Button):
        await self._go(interaction, lambda current, total: min(total or current + 1, current + 1))

    @discord.ui.button(label='>>', style=discord.ButtonStyle.gray, custom_id="25")
    async def increasetoend(self, interaction: discord.Interaction, button: Button):
        await self._go(interaction, lambda current, total: total or current)

if __name__ == "__main__":
    url = "https://18comic.vip/album/622529"
    print(jm_crawl(url))
