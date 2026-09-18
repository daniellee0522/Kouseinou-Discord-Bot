import requests
import discord
import re
import asyncio
import threading
from bs4 import BeautifulSoup
from urllib.parse import quote
from DrissionPage import WebPage, ChromiumOptions
from functions.brand import SUPJAV
from utils.ttl_cache import async_ttl_cache

_browser = None
_browser_lock = threading.Lock()


def _get_browser():
    global _browser
    if _browser is None:
        with _browser_lock:
            if _browser is None:
                co = ChromiumOptions("chromium")
                co.headless(True)
                co.set_user_agent("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36")
                _browser = WebPage(mode='d', chromium_options=co)
    return _browser


def _sync_crawl(url, wait_selector, timeout):
    global _browser
    # 每次都整個開新的 Chromium 再關掉太慢（啟動瀏覽器本身就要好幾秒），
    # 而且每次啟動都會讓 Dock 閃一下圖示；改成共用同一個瀏覽器、每次只開關分頁。
    browser = _get_browser()
    try:
        tab = browser.new_tab()
        try:
            tab.get(url)
            # 死等固定秒數太浪費：大部分情況內容早就載完了。改成等真正要用的
            # 選擇器出現就提早返回，最慢還是封頂在 timeout 秒（跟原本行為一樣）。
            if wait_selector:
                tab.wait.eles_loaded(f'css:{wait_selector}', timeout=timeout)
            else:
                tab.wait(timeout)
            return tab.html
        finally:
            tab.close()
    except Exception:
        # 瀏覽器可能已經死掉，丟掉重建，下次呼叫會自動重新啟動
        _browser = None
        raise


async def chrome_crawl(url, wait_selector=None, timeout=3):
    return await asyncio.to_thread(_sync_crawl, url, wait_selector, timeout)

@async_ttl_cache(ttl_seconds=300, key_arg="keyword")
async def supjav_search_embed(keyword):
    # supjav 的番號跟網址無關（不像 missav 可以直接拼 URL），只能靠搜尋頁取第一筆結果。
    # 搜尋頁用一般 requests 會被擋掉，所以跟 supjav_crawl 一樣改用無頭瀏覽器爬取。
    # 番號常用「-」分隔（如 PKPD-204），但 supjav 搜尋用空格分隔效果較好，所以先轉換。
    keyword = keyword.replace('-', ' ')
    url = f'https://supjav.com/?s={quote(keyword)}'
    try:
        html = await chrome_crawl(url, wait_selector='div.posts.clearfix')
        soup = BeautifulSoup(html, 'html.parser')
        a_element = soup.select_one("div.posts.clearfix > div.post > a.img")
        img_element = a_element.find('img') if a_element else None

        if a_element and img_element:
            href = a_element.get('href')
            title = img_element.get('alt', '無法找到 title')
            src = img_element.get('data-original', '無法找到 src')
            src = re.sub(r'^(.*?)(!.*)?$', r'\1', src)
        else:
            return None
    except Exception:
        return None

    if not href:
        return None

    embed = discord.Embed(title=title, url=href, color=SUPJAV["color"])
    embed.set_image(url=f"https://enderdaniel.work/pic/img?url={src}")
    embed.set_author(name=SUPJAV["name"], url='https://supjav.com/', icon_url=SUPJAV["icon_url"])

    return embed

async def supjav_crawl(url):
    image_url = None
    response = await chrome_crawl(url, wait_selector='#player-wrap')
    soup = BeautifulSoup(response, 'html.parser')
    title = soup.title.text.strip()
    if not title:
        title = "無法取得標題"

    player_div = soup.find("div", id="player-wrap")

    if player_div and "style" in player_div.attrs:
        style = player_div["style"]
        match = re.search(r'url\((.*?)\)', style)
        if match:
            image_url = match.group(1)

    embed = discord.Embed(title=title, url=url, color=SUPJAV["color"])
    if image_url:
        embed.set_image(url=f"https://enderdaniel.work/pic/img?url={image_url}")
        embed.set_author(name=SUPJAV["name"], url="https://supjav.com/", icon_url=SUPJAV["icon_url"])
    return embed

if __name__ == '__main__':
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }
    url = "https://proxy.enderdaniel.work/ABP+123"
    response = requests.get(url,headers=headers)
    if response.status_code != 200:
        print(response.status_code)

    soup = BeautifulSoup(response.text, 'html.parser')
    a = soup
    print(a)
