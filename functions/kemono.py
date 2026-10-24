# kemono（kemono.su 已停用，現在是 kemono.cr）與同一套系統的 coomer（coomer.st）的貼文 / 創作者預覽，
# 貼文圖片用跟 nhentai 一樣的翻頁。API 一定要帶 Accept: text/css，不然回 403。
# 圖片來源用 img.kemono.cr 的縮圖（600px 寬、約 40KB、0.5 秒）：原圖主機 n1~n4.kemono.cr 常常 40 秒以上沒回應。
# 有設定圖床時一樣上傳到 Discord（kemono 換過好幾次網域，舊訊息的圖才不會跟著失效），沒有就直接用縮圖網址。
import re
from urllib.parse import quote
from datetime import datetime, timezone

import aiohttp
import discord
from bs4 import BeautifulSoup
from discord.ui import Button, View

from utils.ttl_cache import async_ttl_cache
from functions.cdn_pages import (apply_page, cdn_page_image, embed_thread_hint, strip_fragment,
                                 total_pages, current_page, JumpModal, reply_with_edit,
                                 message_lock, edit_attachments)

SITES = {
    "kemono": {
        "name": "kemono",
        "icon_url": "https://www.google.com/s2/favicons?domain=kemono.cr&sz=128",
        "color": 0xE8A17D,
        "base": "https://kemono.cr",
        "img": "https://img.kemono.cr",
    },
    "coomer": {
        "name": "coomer",
        "icon_url": "https://www.google.com/s2/favicons?domain=coomer.st&sz=128",
        "color": 0x2C7FB8,
        "base": "https://coomer.st",
        "img": "https://img.coomer.st",
    },
}
_HEADERS = {"Accept": "text/css", "Accept-Encoding": "gzip"}
POST_URL = re.compile(r"(kemono|coomer)\.\w+/(\w+)/user/([\w.-]+)/post/(\d+)")

SERVICE_NAMES = {
    "patreon": "Patreon", "fanbox": "pixivFANBOX", "fantia": "Fantia", "gumroad": "Gumroad",
    "subscribestar": "SubscribeStar", "dlsite": "DLsite", "boosty": "Boosty", "afdian": "愛發電",
    "discord": "Discord", "onlyfans": "OnlyFans", "fansly": "Fansly", "candfans": "CandFans",
}


async def _get(session, site, path):
    async with session.get(f"{SITES[site]['base']}/api/v1{path}", headers=_HEADERS, timeout=aiohttp.ClientTimeout(total=15)) as resp:
        if resp.status != 200:
            return None
        return await resp.json(content_type=None)


@async_ttl_cache(ttl_seconds=1800, maxsize=128, key_arg="post_key")
async def _fetch_post(session, post_key):
    """同一篇 30 分鐘內不重抓：翻頁、跳頁、預載共用。失敗丟例外（不進快取）。post_key = "<站>/<API 路徑>"。"""
    site, path = post_key.split("/", 1)
    data = await _get(session, site, f"/{path}")
    if not data or "post" not in data:
        raise LookupError(f"kemono post {post_key} not found")
    return data


def _post_path(service, user_id, post_id):
    return f"{service}/user/{user_id}/post/{post_id}"


def _post_key(site, service, user_id, post_id):
    return f"{site}/{_post_path(service, user_id, post_id)}"


def kemono_gallery(site, service, user_id, post_id):
    return f"{site}-{service}-{user_id}-{post_id}"


async def resolve_short_post(session, site, service, post_id):
    """沒有創作者 ID 的短網址 /<平台>/post/<id>：API 會回傳完整位置，回傳創作者 ID；找不到回傳 None。"""
    data = await _get(session, site, f"/{service}/post/{post_id}")
    return (data or {}).get("artist_id")


def post_images(site, data):
    """縮圖網址清單，順序跟 kemono 網頁上的一樣"""
    return [f"{SITES[site]['img']}/thumbnail/data{p['path']}" for p in data.get("previews") or []
            if p.get("type") == "thumbnail" and p.get("path")]


async def kemono_page_image(session, cdn, site, service, user_id, post_id, page_num, thread_hint=None, inline=False):
    """第 page_num 頁（從 1 開始）：有圖床就是 Discord CDN 網址（並背景預載整篇），否則是 kemono 縮圖網址。"""
    async def images():
        return post_images(site, await _fetch_post(session, _post_key(site, service, user_id, post_id)))

    async def src_of(n):
        return (await images())[n - 1]

    async def total():
        return len(await images())

    url = await cdn_page_image(cdn, kemono_gallery(site, service, user_id, post_id), page_num, src_of, total,
                               thread_hint=thread_hint, inline=inline)
    return url or await src_of(int(page_num))


async def kemono_post_embed(session, site, service, user_id, post_id, cdn=None):
    """回傳 (embed, 頁數)；頁數 > 1 時呼叫端附上 KemonoView 翻頁。找不到貼文回傳 (None, 0)。"""
    try:
        data = await _fetch_post(session, _post_key(site, service, user_id, post_id))
    except LookupError:
        return None, 0
    post = data["post"]
    info = SITES[site]
    base = info["base"]
    creator = await _get(session, site, f"/{service}/user/{user_id}/profile")

    content = BeautifulSoup(post.get("content") or post.get("substring") or "", "html.parser").get_text("\n").strip()
    embed = discord.Embed(title=(post.get("title") or "（無標題）")[:256], url=f"{base}/{_post_path(service, user_id, post_id)}",
                          description=content[:350] + ("…" if len(content) > 350 else ""),
                          color=info["color"])
    embed.set_author(name=info["name"], url=base, icon_url=info["icon_url"])
    embed.set_thumbnail(url=f"{info['img']}/icons/{service}/{user_id}")
    name = creator.get("name") if creator else user_id
    embed.add_field(name="作者", value=f"[{name}]({base}/{service}/user/{user_id})")
    embed.add_field(name="平台", value=SERVICE_NAMES.get(service, service))
    if post.get("published"):
        try:
            embed.timestamp = datetime.fromisoformat(post["published"]).replace(tzinfo=timezone.utc)  # API 給的是 UTC
        except ValueError:
            pass
    if data.get("videos"):
        embed.add_field(name="影片", value=str(len(data["videos"])))
    if post.get("tags"):
        embed.add_field(name="標籤", value="、".join(post["tags"])[:1024], inline=False)
    # 壓縮檔、PSD 之類不是圖片的附件（圖片在 previews、影片在 videos）
    files = [f"[{a['name']}]({a.get('server') or base}/data{a['path']}?f={quote(a['name'])})"
             for a in data.get("attachments") or [] if a.get("path") and a.get("name")]
    if files:
        value = ""
        for link in files:
            if len(value) + len(link) + 20 > 1024:  # 留位置給最後的「共 N 個」
                value += f"\n…共 {len(files)} 個"
                break
            value += ("\n" if value else "") + link
        embed.add_field(name="附件", value=value, inline=False)
    if (post.get("embed") or {}).get("url"):
        link = post["embed"]
        embed.add_field(name="外部連結", value=f"[{(link.get('subject') or link['url'])[:200]}]({link['url']})", inline=False)

    images = post_images(site, data)
    if images:
        embed.add_field(name="頁數", value=str(len(images)))
        img = await kemono_page_image(session, cdn, site, service, user_id, post_id, 1, inline=True)
        apply_page(embed, img, 1, cdn, kemono_gallery(site, service, user_id, post_id), colour=info["color"])
    return embed, len(images)


async def kemono_creator_embed(session, site, service, user_id):
    creator = await _get(session, site, f"/{service}/user/{user_id}/profile")
    if not creator:
        return None
    info = SITES[site]
    embed = discord.Embed(title=creator.get("name") or user_id, url=f"{info['base']}/{service}/user/{user_id}",
                          color=info["color"])
    embed.set_author(name=info["name"], url=info["base"], icon_url=info["icon_url"])
    embed.set_thumbnail(url=f"{info['img']}/icons/{service}/{user_id}")
    embed.set_image(url=f"{info['img']}/banners/{service}/{user_id}")
    embed.add_field(name="平台", value=SERVICE_NAMES.get(service, service), inline=True)
    if creator.get("post_count") is not None:
        embed.add_field(name="貼文數", value=str(creator["post_count"]), inline=True)
    if creator.get("updated"):
        embed.set_footer(text=f"最後更新 {creator['updated'][:10]}")
    return embed


async def render_kemono_page(session, cdn, embed: discord.Embed, target):
    """翻頁、跳頁共用：只換圖片與頁碼。回傳實際的頁碼。"""
    site, service, user_id, post_id = POST_URL.search(strip_fragment(embed.url)).groups()
    total = total_pages(embed)
    target = max(1, min(int(target), total)) if total else max(1, int(target))
    img = await kemono_page_image(session, cdn, site, service, user_id, post_id, target,
                                  thread_hint=embed_thread_hint(embed), inline=True)
    apply_page(embed, img, target, cdn, kemono_gallery(site, service, user_id, post_id), colour=SITES[site]["color"])
    return target


class KemonoView(View):
    def __init__(self, session: aiohttp.ClientSession = None, embed: discord.Embed = None):
        super().__init__(timeout=None)
        self.session = session
        # 舊訊息共用 persistent View，每次操作都從該訊息讀取頁碼
        if embed is not None:
            self.middle_button.label = f"{current_page(embed)}/{total_pages(embed)}"

    async def _render(self, interaction: discord.Interaction, embed: discord.Embed, target):
        cdn = getattr(interaction.client, "image_cdn", None)
        target = await render_kemono_page(self.session or interaction.client.session, cdn, embed, target)
        self.middle_button.label = f"{target}/{total_pages(embed)}"
        return dict(embed=embed, view=self, attachments=edit_attachments(embed))

    async def _go(self, interaction: discord.Interaction, target_of):
        embed = interaction.message.embeds[0]

        async def work():
            async with message_lock(interaction.message.id):
                return await self._render(interaction, embed, target_of(current_page(embed), total_pages(embed)))

        await reply_with_edit(interaction, work)

    @discord.ui.button(label='<<', style=discord.ButtonStyle.gray, custom_id="kemono:first")
    async def decreasetostart(self, interaction: discord.Interaction, button: Button):
        await self._go(interaction, lambda current, total: 1)

    @discord.ui.button(label='<', style=discord.ButtonStyle.gray, custom_id="kemono:prev")
    async def decrease(self, interaction: discord.Interaction, button: Button):
        await self._go(interaction, lambda current, total: max(1, current - 1))

    @discord.ui.button(label="-", style=discord.ButtonStyle.primary, custom_id="kemono:jump")
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

    @discord.ui.button(label='>', style=discord.ButtonStyle.gray, custom_id="kemono:next")
    async def increase(self, interaction: discord.Interaction, button: Button):
        await self._go(interaction, lambda current, total: min(total or current + 1, current + 1))

    @discord.ui.button(label='>>', style=discord.ButtonStyle.gray, custom_id="kemono:last")
    async def increasetoend(self, interaction: discord.Interaction, button: Button):
        await self._go(interaction, lambda current, total: total or current)
