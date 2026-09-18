import discord
from bs4 import BeautifulSoup
import asyncio
import os
from functions.jable import jable_embed
from functions.supav import supjav_search_embed
from functions.brand import MISSAV
from utils.ttl_cache import async_ttl_cache

def judge_valid_missav_url(url_content):
    soup = BeautifulSoup(url_content, 'html.parser')
    title = soup.find('meta', attrs={'property': 'og:title'})
    main_content = parse_main_content(url_content)

    if "MissAV | 免費高清AV在線看" == title['content']:
        if main_content:
            if "找不到頁面" in main_content or "404" in main_content:
                return False
            else:
                return True
    return True


@async_ttl_cache(ttl_seconds=300, key_arg="digit")
async def fetch_missav_embed(session, digit):
    """回傳 missav embed；頁面確定不存在（假 200）時回傳 None；
    爬蟲本身失敗則讓例外往外拋，呼叫端可以顯示暫時無法取得資料。
    成功的結果（含 None）才會被快取，例外不快取，避免暫時性錯誤被記住太久。"""
    link = f"https://missav.ai/{digit}"
    response = await session.request(link)
    if not response:
        raise ValueError("MissAV 無回應")
    if not judge_valid_missav_url(response):
        return None

    soup = BeautifulSoup(response, 'html.parser')
    description = soup.find('meta', attrs={'name': 'description'})
    title = soup.find('meta', attrs={'property': 'og:title'})
    image = soup.find('meta', attrs={'property': 'og:image'})
    embed = discord.Embed(title=title['content'], url=link, color=MISSAV["color"])
    if image:
        embed.set_image(url=image['content'])
    if description:
        embed.description = description['content']
    embed.set_author(name=MISSAV["name"], url=link, icon_url=MISSAV["icon_url"])
    return embed


async def missav_fallback_embed(jable_session, digit):
    """missav 判定為「找不到頁面」(假 200) 時使用：同時查 jable 跟 supjav，
    誰先驗證有結果就用誰，優先權 jable > supjav；兩邊都沒有則回傳 None。"""
    jable_result, supjav_result = await asyncio.gather(
        jable_embed(jable_session, digit),
        supjav_search_embed(digit),
    )
    if jable_result is not None:
        return jable_result
    if supjav_result is not None:
        return supjav_result
    return None


def parse_main_content(html: str):
    soup = BeautifulSoup(html, 'html.parser')

    main = soup.find('main')
    if not main:
        # print(f"[parse] 找不到 <main>，頁面片段：{soup.get_text()[:200]}")
        return None  # 改成回傳 None，不 raise

    return main.get_text(strip=True)


async def main():
    os.chdir(r"/Users/leechenxsun/python_script/dc/")
    import sys
    sys.path.append(r'/Users/leechenxsun/python_script/dc/')

    from functions.sec5sh import Sec5sh
    session = Sec5sh()
    url = "https://missav.ai/1234"
    response = await session.request(url)
    # status_code = response.status
    soup = BeautifulSoup(response, "html.parser")
    title = soup.find('meta', attrs={'property': 'og:title'})
    content = parse_main_content(response)

    # print(f"Status Code: {status_code}")
    print(f"Title: {title['content'] if title else 'N/A'}")
    print(content)

    print(judge_valid_missav_url(response))

    await session.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
