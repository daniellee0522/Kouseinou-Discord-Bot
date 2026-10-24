# hanime1.me 整站在 Cloudflare 後面，Discord 的爬蟲拿不到預覽，要經過 FlareSolverr。
# 縮圖網址（vdownload.hembed.com）Discord 可以直接抓；網址帶約一個月效期的簽章。
import re

import discord
from bs4 import BeautifulSoup

from utils.ttl_cache import async_ttl_cache

HANIME1 = {
    "name": "Hanime1",
    "icon_url": "https://www.google.com/s2/favicons?domain=hanime1.me&sz=128",
    "color": 0xD31D5D,
}


@async_ttl_cache(ttl_seconds=600, maxsize=128, key_arg="video_id")
async def _fetch(crawler, video_id):
    html = await crawler.request(f"https://hanime1.me/watch?v={video_id}")
    if not html or 'property="og:title"' not in html:
        raise LookupError(f"hanime1 {video_id} failed")
    return html


async def hanime1_embed(crawler, video_id):
    url = f"https://hanime1.me/watch?v={video_id}"
    try:
        soup = BeautifulSoup(await _fetch(crawler, video_id), "html.parser")
    except LookupError:
        return None
    meta = lambda prop: (soup.find("meta", property=prop) or {}).get("content")

    title = soup.select_one("#shareBtn-title")
    title = title.get_text(strip=True) if title else re.sub(r"\s*-\s*Hanime1\.me$", "", meta("og:title") or "")
    embed = discord.Embed(title=title[:256], url=url, color=HANIME1["color"])
    embed.set_author(name=HANIME1["name"], url="https://hanime1.me/", icon_url=HANIME1["icon_url"])
    if meta("og:image"):
        embed.set_image(url=meta("og:image"))

    artist = soup.select_one("#video-artist-name")
    if artist:
        embed.add_field(name="作者", value=artist.get_text(strip=True), inline=True)
    if (duration := meta("og:video:duration")) and duration.isdigit():
        embed.add_field(name="長度", value=f"{int(duration) // 60}:{int(duration) % 60:02d}", inline=True)
    panel = soup.select_one(".video-description-panel")
    if panel and (views := re.search(r"觀看次數：(\S+?)次\s*(\d{4}-\d{2}-\d{2})?", panel.get_text(" "))):
        embed.add_field(name="觀看", value=views.group(1), inline=True)
        if views.group(2):
            embed.set_footer(text=views.group(2))
    # 標籤：「# 作品名」是系列，其餘去掉後面的「(1)」計數
    tags = [re.sub(r"\s*\(\d+\)$", "", a.get_text(strip=True)).lstrip("# ") for a in soup.select(".single-video-tag a")]
    tags = [t for t in dict.fromkeys(tags) if t and not re.fullmatch(r"\d+p", t)]
    if tags:
        embed.add_field(name="標籤", value="、".join(tags)[:1024], inline=False)
    return embed
