# Mobile01 對 Discord 的爬蟲回 403（完全沒有預覽），要經過 FlareSolverr 才拿得到頁面。
# 文章圖片放在 attach.mobile01.com，Discord 可以直接抓，不用經過圖床。
import discord
from bs4 import BeautifulSoup

from utils.ttl_cache import async_ttl_cache

MOBILE01 = {
    "name": "Mobile01",
    "icon_url": "https://www.google.com/s2/favicons?domain=mobile01.com&sz=128",
    "color": 0x2E8B57,
}
# 沒有附圖的文章 og:image 會是這張網站 logo，不顯示
_DEFAULT_IMAGE = "mobile01-facebook.jpg"


@async_ttl_cache(ttl_seconds=600, maxsize=128, key_arg="url")
async def _fetch(crawler, url):
    html = await crawler.request(url)
    if not html:
        raise LookupError(f"mobile01 {url} failed")
    return html


async def mobile01_embeds(crawler, url):
    """回傳 embed 清單：文章前 4 張圖用同一個 url 組成 Discord 相簿；抓不到回傳 None"""
    soup = BeautifulSoup(await _fetch(crawler, url), "html.parser")
    title = soup.find("h1")
    article = soup.select_one("article")
    if title is None or article is None:
        return None

    body = article.get_text("\n", strip=True)
    embed = discord.Embed(title=title.get_text(strip=True)[:256], url=url,
                          description=body[:350] + ("…" if len(body) > 350 else ""), color=MOBILE01["color"])
    crumbs = [a.get_text(strip=True) for a in soup.select("[class*=bread] a")]
    # 麵包屑會重複出現兩次（頁首、頁尾），取第一組的最後一層看板名稱
    board = crumbs[:len(crumbs) // 2][-1] if len(crumbs) >= 2 else None
    embed.set_author(name=f"{MOBILE01['name']}｜{board}" if board else MOBILE01["name"],
                     url="https://www.mobile01.com/", icon_url=MOBILE01["icon_url"])
    author = soup.select_one(".c-authorInfo__id")
    if author:
        embed.add_field(name="作者", value=author.get_text(strip=True), inline=True)
    notes = [e.get_text(strip=True) for e in soup.select(".o-fNotes.o-fSubMini")]
    # 樓主那一列依序是：發文時間、瀏覽數
    if len(notes) >= 2 and notes[1].isdigit():
        embed.add_field(name="瀏覽", value=notes[1], inline=True)
    if notes:
        embed.set_footer(text=notes[0])

    images = []
    for img in article.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        if "attach.mobile01.com/attach/" in src and src not in images:
            images.append(src)
    if not images:
        og = soup.find("meta", property="og:image")
        if og and _DEFAULT_IMAGE not in og["content"]:
            images = [og["content"]]
    if not images:
        return [embed]
    embeds = []
    for index, image in enumerate(images[:4]):
        item = embed if index == 0 else discord.Embed(url=url, color=MOBILE01["color"])
        item.set_image(url=image)
        embeds.append(item)
    return embeds
