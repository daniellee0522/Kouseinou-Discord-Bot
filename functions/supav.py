import requests
import discord
import re
from io import BytesIO
from PIL import Image
from bs4 import BeautifulSoup
from DrissionPage import WebPage, ChromiumOptions
import config


async def chrome_crawl(url):
    co = ChromiumOptions("chromium")
    co.headless(True)
    co.set_user_agent("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36")
    browser = WebPage(mode='d',chromium_options=co)
    browser.get(url)
    browser.wait(3)
    data = browser.html
    print(browser.user_agent)
    browser.quit()

    return data

def supav_embed(id):
    url = f'https://supjav.com/?s={id}'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }
    try:
        page = requests.get(url, headers=headers)
        soup = BeautifulSoup(page.text, 'html.parser')
        a_element = soup.select_one("body > div.main > div > div.content > div.posts.clearfix > div > a")
        img_element = soup.select_one("body > div.main > div > div.content > div.posts.clearfix > div > a > img")
    
    # 提取 href 和 src
        if a_element and img_element:
            href = a_element.get('href', '無法找到 href')
            title = img_element.get('alt', '無法找到 title')
            src = img_element.get('data-original', '無法找到 src')
            src = re.sub(r'^(.*?)(!.*)?$', r'\1', src)
            
            # print("href:", href)
            # print("src:", src)
        else:
            return 'no video found'
    except:
        return 'no video found'
    
    embed = discord.Embed(title=title, url=href)
    embed.set_image(url=f"{config.PIC_PROXY_URL}/img?url={src}")
    embed.set_author(name='supjav', url='https://supjav.com/')

    return embed

async def supjav_crawl(url):
    image_url = None
    response = await chrome_crawl(url)
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

    embed = discord.Embed(title=title, url=url)
    if image_url:
        embed.set_image(url=f"{config.PIC_PROXY_URL}/img?url={image_url}")
        embed.set_author(name="Supjav", url="https://supjav.com/")
    return embed

if __name__ == '__main__':
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }
    url = config.MEDIA_BASE_URL + "/ABP+123"
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(response.status_code)

    soup = BeautifulSoup(response.text, 'html.parser')
    a = soup
    print(a)
