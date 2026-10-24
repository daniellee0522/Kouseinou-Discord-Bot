# iwara 的網頁跟 API（api.iwara.tv）都在 Cloudflare 後面，要經過 FlareSolverr；
# 縮圖在 i.iwara.tv，Discord 可以直接抓。
import html
import json
import re
from datetime import datetime

import discord

from utils.ttl_cache import async_ttl_cache

IWARA = {
    "name": "Iwara",
    "icon_url": "https://www.google.com/s2/favicons?domain=iwara.tv&sz=128",
    "color": 0x00A0D2,
}
RATINGS = {"general": "一般", "ecchi": "R-18"}


# 圖片貼文的 GIF 原檔不超過這個大小才放原檔（才會動），否則用 large 縮圖
GIF_LIMIT = 8 * 1024 * 1024


@async_ttl_cache(ttl_seconds=600, maxsize=128, key_arg="path")
async def _fetch(crawler, path):
    """path 例如 video/<id>、image/<id>"""
    text = await crawler.request(f"https://api.iwara.tv/{path}")
    if not text:
        raise LookupError(f"iwara {path} failed")
    # 經過 FlareSolverr 時 JSON 會被瀏覽器包在 <pre> 裡
    if "<pre" in text:
        text = html.unescape(re.search(r"<pre[^>]*>(.*?)</pre>", text, re.S).group(1))
    data = json.loads(text)
    if "id" not in data:
        raise LookupError(f"iwara {path}: {data.get('message')}")
    return data


def _base_embed(item, kind):
    """影片、圖片貼文共用的標題、作者、觀看數、分級、標籤"""
    url = f"https://www.iwara.tv/{kind}/{item['id']}" + (f"/{item['slug']}" if item.get("slug") else "")
    embed = discord.Embed(title=(item.get("title") or item["id"])[:256], url=url,
                          description=(item.get("body") or "")[:350], color=IWARA["color"])
    embed.set_author(name=IWARA["name"], url="https://www.iwara.tv/", icon_url=IWARA["icon_url"])

    user = item.get("user") or {}
    if user.get("username"):
        embed.add_field(name="作者", value=f"[{user.get('name') or user['username']}](https://www.iwara.tv/profile/{user['username']})",
                        inline=True)
    embed.add_field(name="觀看 / 喜歡", value=f"{item.get('numViews', 0)} / {item.get('numLikes', 0)}", inline=True)
    if item.get("rating"):
        embed.add_field(name="分級", value=RATINGS.get(item["rating"], item["rating"]), inline=True)
    tags = [t.get("id") for t in item.get("tags") or [] if t.get("id")]
    if tags:
        embed.add_field(name="標籤", value="、".join(tags)[:1024], inline=False)
    if item.get("createdAt"):
        embed.timestamp = datetime.fromisoformat(item["createdAt"].replace("Z", "+00:00"))
    return embed


async def iwara_embed(crawler, video_id):
    try:
        video = await _fetch(crawler, f"video/{video_id}")
    except (LookupError, ValueError, AttributeError):
        return None
    embed = _base_embed(video, "video")

    file = video.get("file") or {}
    if file.get("id"):
        embed.set_image(url=f"https://i.iwara.tv/image/original/{file['id']}/thumbnail-{int(video.get('thumbnail') or 0):02d}.jpg")
    elif video.get("embedUrl"):
        # 嵌入 YouTube 的影片沒有自己的檔案，附上原始連結讓 Discord 另外預覽
        embed.add_field(name="嵌入影片", value=video["embedUrl"], inline=False)
    return embed


def _image_url(file):
    if file.get("mime") == "image/gif" and (file.get("size") or 0) <= GIF_LIMIT:
        return f"https://i.iwara.tv/image/original/{file['id']}/{file['name']}"
    return f"https://i.iwara.tv/image/large/{file['id']}/{file['id']}.jpg"


async def iwara_image_embed(crawler, image_id):
    """圖片貼文：回傳 embed 清單，前 4 張圖用同一個 url 組成 Discord 相簿；抓不到回傳 None"""
    try:
        post = await _fetch(crawler, f"image/{image_id}")
    except (LookupError, ValueError, AttributeError):
        return None
    embed = _base_embed(post, "image")
    files = [f for f in post.get("files") or [] if f.get("id")]
    if len(files) > 1:
        embed.add_field(name="張數", value=str(post.get("numImages") or len(files)), inline=True)
    if not files:
        return [embed]
    embeds = []
    for index, file in enumerate(files[:4]):
        item = embed if index == 0 else discord.Embed(url=embed.url, color=IWARA["color"])
        item.set_image(url=_image_url(file))
        embeds.append(item)
    return embeds
