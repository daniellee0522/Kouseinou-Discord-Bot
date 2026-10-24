# hitomi.la 本子預覽，翻頁跟 nhentai 一樣。
# 本子資料（galleries/<id>.js）不用解盾就拿得到；圖片網址要照 hitomi 的 gg.js 規則計算，
# 而且下載一定要帶 Referer，Discord 自己抓不到 —— 所以圖片只能經過圖床上傳，沒有圖床時只顯示文字資訊。
import json
import re

import aiohttp
import discord
from discord.ui import Button, View

from utils.ttl_cache import async_ttl_cache
from functions.discord_cdn import HeaderSrc
from functions.cdn_pages import (apply_page, cdn_page_image, embed_thread_hint, strip_fragment,
                                 total_pages, current_page, JumpModal, reply_with_edit,
                                 message_lock, edit_attachments)

HITOMI = {
    "name": "hitomi",
    "icon_url": "https://www.google.com/s2/favicons?domain=hitomi.la&sz=128",
    "color": 0x29313D,
}
DOMAIN = "gold-usergeneratedcontent.net"
HEADERS = {
    "Referer": "https://hitomi.la/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
}
GALLERY_URL = re.compile(r"hitomi\.la/galleries/(\d+)\.html")


async def _get_text(session, url):
    async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=15)) as resp:
        if resp.status != 200:
            raise LookupError(f"hitomi {url} -> {resp.status}")
        return await resp.text()


@async_ttl_cache(ttl_seconds=1800, maxsize=128, key_arg="gallery_id")
async def fetch_gallery(session, gallery_id):
    text = await _get_text(session, f"https://ltn.{DOMAIN}/galleries/{gallery_id}.js")
    return json.loads(text.split("=", 1)[1])


@async_ttl_cache(ttl_seconds=300, maxsize=1, key_arg="key")
async def _fetch_gg(session, key="gg"):
    """gg.js 決定圖片主機與路徑，內容會定期更換，5 分鐘重抓一次"""
    js = await _get_text(session, f"https://ltn.{DOMAIN}/gg.js")
    default = int(re.search(r"var o = (\d)", js).group(1))
    value = int(re.search(r"o = (\d); break;", js).group(1))
    cases = {int(c) for c in re.findall(r"case (\d+):", js)}
    base = re.search(r"b: '(\d+/)'", js).group(1)
    return cases, default, value, base


async def image_src(session, file):
    """對應 hitomi common.js 的 url_from_url_from_hash(..., 'webp')"""
    cases, default, value, base = await _fetch_gg(session, "gg")
    h = file["hash"]
    g = int(h[-1] + h[-3:-1], 16)
    sub = 1 + (value if g in cases else default)
    return HeaderSrc(f"https://w{sub}.{DOMAIN}/{base}{g}/{h}.webp", HEADERS)


def hitomi_gallery(gallery_id):
    return f"hitomi-{gallery_id}"


async def hitomi_page_image(session, cdn, gallery_id, page_num, thread_hint=None, inline=False):
    """第 page_num 頁的 Discord CDN 網址；沒有圖床或上傳失敗回傳 None。"""
    async def files():
        return (await fetch_gallery(session, gallery_id))["files"]

    async def src_of(n):
        return await image_src(session, (await files())[n - 1])

    async def total():
        return len(await files())

    return await cdn_page_image(cdn, hitomi_gallery(gallery_id), page_num, src_of, total,
                                thread_hint=thread_hint, inline=inline)


def _names(items, key):
    return [i[key] for i in items or [] if i.get(key)]


async def hitomi_embed(session, gallery_id, page_num=1, cdn=None):
    """回傳 (embed, 頁數)；找不到本子回傳 (None, 0)。"""
    try:
        info = await fetch_gallery(session, gallery_id)
    except (LookupError, ValueError):
        return None, 0
    url = f"https://hitomi.la/galleries/{gallery_id}.html"
    embed = discord.Embed(title=(info.get("japanese_title") or info.get("title") or gallery_id)[:256], url=url,
                          color=HITOMI["color"])
    embed.set_author(name=HITOMI["name"], url="https://hitomi.la/", icon_url=HITOMI["icon_url"])
    if info.get("japanese_title") and info.get("title"):
        embed.description = info["title"][:350]

    artists = _names(info.get("artists"), "artist") + _names(info.get("groups"), "group")
    if artists:
        embed.add_field(name="作者", value="、".join(artists)[:1024])
    parodies = _names(info.get("parodys"), "parody")
    if parodies:
        embed.add_field(name="原作", value="、".join(parodies)[:1024])
    if info.get("type"):
        embed.add_field(name="類型", value=info["type"])
    if info.get("language_localname"):
        embed.add_field(name="語言", value=info["language_localname"])
    tags = [("♀" if t.get("female") == "1" else "♂" if t.get("male") == "1" else "") + t["tag"]
            for t in info.get("tags") or [] if t.get("tag")]
    if tags:
        embed.add_field(name="標籤", value=", ".join(tags)[:1024], inline=False)

    pages = len(info.get("files") or [])
    if pages:
        embed.add_field(name="頁數", value=str(pages))
        page_num = max(1, min(int(page_num), pages))
        img = await hitomi_page_image(session, cdn, gallery_id, page_num, inline=True)
        if img:
            apply_page(embed, img, page_num, cdn, hitomi_gallery(gallery_id), colour=HITOMI["color"])
        else:
            pages = 0  # 沒有圖床就沒有圖，也不需要翻頁
    return embed, pages


async def render_hitomi_page(session, cdn, embed: discord.Embed, target):
    """翻頁、跳頁共用：只換圖片與頁碼。回傳實際的頁碼；拿不到圖時頁面不變。"""
    gallery_id = GALLERY_URL.search(strip_fragment(embed.url)).group(1)
    total = total_pages(embed)
    target = max(1, min(int(target), total)) if total else max(1, int(target))
    img = await hitomi_page_image(session, cdn, gallery_id, target, thread_hint=embed_thread_hint(embed), inline=True)
    if not img:
        return current_page(embed)
    apply_page(embed, img, target, cdn, hitomi_gallery(gallery_id), colour=HITOMI["color"])
    return target


class HitomiView(View):
    def __init__(self, session: aiohttp.ClientSession = None, embed: discord.Embed = None):
        super().__init__(timeout=None)
        self.session = session
        # 舊訊息共用 persistent View，每次操作都從該訊息讀取頁碼
        if embed is not None:
            self.middle_button.label = f"{current_page(embed)}/{total_pages(embed)}"

    async def _render(self, interaction: discord.Interaction, embed: discord.Embed, target):
        cdn = getattr(interaction.client, "image_cdn", None)
        target = await render_hitomi_page(self.session or interaction.client.session, cdn, embed, target)
        self.middle_button.label = f"{target}/{total_pages(embed)}"
        return dict(embed=embed, view=self, attachments=edit_attachments(embed))

    async def _go(self, interaction: discord.Interaction, target_of):
        embed = interaction.message.embeds[0]

        async def work():
            async with message_lock(interaction.message.id):
                return await self._render(interaction, embed, target_of(current_page(embed), total_pages(embed)))

        await reply_with_edit(interaction, work)

    @discord.ui.button(label='<<', style=discord.ButtonStyle.gray, custom_id="hitomi:first")
    async def decreasetostart(self, interaction: discord.Interaction, button: Button):
        await self._go(interaction, lambda current, total: 1)

    @discord.ui.button(label='<', style=discord.ButtonStyle.gray, custom_id="hitomi:prev")
    async def decrease(self, interaction: discord.Interaction, button: Button):
        await self._go(interaction, lambda current, total: max(1, current - 1))

    @discord.ui.button(label="-", style=discord.ButtonStyle.primary, custom_id="hitomi:jump")
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

    @discord.ui.button(label='>', style=discord.ButtonStyle.gray, custom_id="hitomi:next")
    async def increase(self, interaction: discord.Interaction, button: Button):
        await self._go(interaction, lambda current, total: min(total or current + 1, current + 1))

    @discord.ui.button(label='>>', style=discord.ButtonStyle.gray, custom_id="hitomi:last")
    async def increasetoend(self, interaction: discord.Interaction, button: Button):
        await self._go(interaction, lambda current, total: total or current)
