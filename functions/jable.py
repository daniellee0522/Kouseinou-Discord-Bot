import discord
from bs4 import BeautifulSoup
from functions.brand import JABLE
from utils.ttl_cache import async_ttl_cache


@async_ttl_cache(ttl_seconds=300, key_arg="digit")
async def jable_embed(session, digit):
    """依番號組出 jable.tv 的網址並爬取。jable 對不存在的番號會回傳真正的
    HTTP 404（不像 missav 用 FlareSolver 解盾後拿到的是假 200），Sec5sh.request
    對非 200/403 的回應本來就會回傳 None，所以這裡直接把 None 當作找不到。"""
    url = f"https://jable.tv/videos/{digit.lower()}/"
    try:
        response = await session.request(url)
    except Exception:
        return None
    if not response:
        return None

    soup = BeautifulSoup(response, 'html.parser')
    title = soup.find('meta', attrs={'property': 'og:title'})
    if not title:
        return None
    image = soup.find('meta', attrs={'property': 'og:image'})

    embed = discord.Embed(title=title['content'], url=url, color=JABLE["color"])
    if image:
        embed.set_image(url=image['content'])
    embed.set_author(name=JABLE["name"], url=url, icon_url=JABLE["icon_url"])

    return embed
