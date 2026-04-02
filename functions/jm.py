import urllib.request as req
from bs4 import BeautifulSoup
import discord
from curl_cffi import requests
from discord.ui import Button, View
import json
import re
import io
import sys
from io import BytesIO
from pathlib import Path
import aiohttp
from PIL import Image
import hashlib
import asyncio
from discord.ext import tasks, commands
import config

sys.stdout = io.TextIOWrapper(
    sys.stdout.buffer, encoding='utf-8')

_cookies_path = Path(__file__).parent.parent / 'data' / 'cookies.json'
with open(_cookies_path, 'r', encoding='utf8') as _f:
    _cookies = json.load(_f)

public_headers = {
    'cookie': _cookies.get('jm_cookie', ''),
    'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0"
}

def jm_crawl(url):
    page = 0
    urlServer = "http://localhost:8191/v1"
    if True:
        request = requests.get(url, headers={
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,'
                    'application/signed-exchange;v=b3;q=0.7',
            'accept-language': 'zh-TW,zh;q=0.9',
            'sec-ch-ua': '"Not.A/Brand";v="8", "Chromium";v="114", "Google Chrome";v="114"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'none',
            'sec-fetch-user': '?1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 '
                        'Safari/537.36',
        })
        html = request.text
        print(html)
        soup = BeautifulSoup(html, 'lxml')
    else:
        urlServer = "http://localhost:8191/v1"
        payload = {
            "cmd": "request.get",
            "url": url,
            "maxTimeout": 60000,
            "session": "comic_session_1",
            # "headers": {
                # "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                # "Referer": "https://18comic.vip/",
                # "Accept-Language": "zh-TW,zh;q=0.9",
                # },
            "browserParams": {
                "browserArgs": [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--blink-settings=imagesEnabled=false"
                ]
            }
        }
        html = requests.post(urlServer, json=payload).json()["solution"]["response"]
        soup = BeautifulSoup(html, 'html.parser')

    # print(soup)
    title = soup.title.text
    try:
        title = title[:title.index("|")]
    except:
        pass


    # id 部分
    album_id = extract_number_from_url(url)
    if album_id == None:
        scripts = soup.find_all("script")
        pattern = re.compile(r'/album/(\d+)/')

        for script in scripts:
            if script.string:
                match = pattern.search(script.string)
                if match:
                    album_id = match.group(1)
                    break

        # page = 0

    # 取得頁數
    anchors = soup.find_all('a')

    if anchors != []:
        url2 = f"https://18comic.vip/photo/{album_id}"
        
        html = requests.get(url2, headers=public_headers).text
        soup2 = BeautifulSoup(html, 'html.parser')
        options = soup2.find_all('option')
        page = int(options[-1].get('value'))+1
        
    else:
        tags = soup.find_all('div', class_='p-t-5 p-b-5')
        for i,tag in enumerate(tags):
            if "頁數" in tag.get_text(strip=True):
                page = int(tag.get_text(strip=True).split("：")[-1])

    return title, page, album_id 


def jm_embed(url):
    id = extract_number_from_url(url)
    if id == None:
        title, page, id = jm_crawl(url)
    else:
        title, page, _ = jm_crawl(url)

    embed = discord.Embed(title=title, url=url, color=0xe37e31)
    embed.set_author(
        name="禁漫天堂", icon_url="https://i.imgur.com/dYVERFN.png")
    embed.add_field(name="頁數", value=page)
    embed.set_thumbnail(url=f"{config.PIC_PROXY_URL}/transform?url=https://cdn-msp3.18comic.org/media/albums/{id}.jpg")
    url3 = f"https://cdn-msp.18comic.org/media/photos/{id}/00001.webp"

    # 該處裡的清單

    embed.set_image(url=f"{config.PIC_PROXY_URL}/transform?url={url3}")

    return embed


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


class NumberView3(View):
    def __init__(self, embed:discord.Embed=None):
        super().__init__(timeout=None)
        # self.message = message
        self.number = 1
        self.domain = f"{config.PIC_PROXY_URL}/transform?url="

        if embed != None:
            embed_dict = {i.name: i.value for i in embed.fields}
            num = embed_dict["頁數"]
            
            # 設置中間按鈕的標籤
            self.middle_button.label = f"{self.number}/{num}"

    @discord.ui.button(label='<<', style=discord.ButtonStyle.gray, custom_id="21")
    async def decreasetostart(self, interaction: discord.Interaction, button: Button):
        self.number = 1
        page_num = fillnum(self.number)
        embed = interaction.message.embeds[0]
        embed_dict = {i.name: i.value for i in embed.fields}
        title = embed.url
        id = extract_number_from_url(title)
        num = embed_dict["頁數"]
        url = f"https://cdn-msp.18comic.org/media/photos/{id}/00001.webp"
        


        embed.set_image(url= self.domain + url)

        self.middle_button.label = str(self.number)+"/" + num

        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.defer()
        channel = interaction.client.get_channel(config.JM_LOG_CHANNEL_ID)
        # await channel.send(f"{self.domain}{url}")

    @discord.ui.button(label='<', style=discord.ButtonStyle.gray, custom_id="22")
    async def decrease(self, interaction: discord.Interaction, button: Button):
        embed = interaction.message.embeds[0]
        embed_dict = {i.name: i.value for i in embed.fields}
        num = embed_dict["頁數"]
        url = embed.image.url
        title = embed.url
        id = extract_number_from_url(title)

        self.number = int(url[-10:-5])
        if self.number > 1:
            self.number -= 1

        url = f"https://cdn-msp.18comic.org/media/photos/{id}/{fillnum(self.number)}.webp"

        embed.set_image(url=self.domain+url)

        self.middle_button.label = str(self.number)+"/" + num

        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.defer()
        # channel = interaction.client.get_channel(config.JM_LOG_CHANNEL_ID)
        # await channel.send(f"{self.domain}{url}")

    @discord.ui.button(label="-", style=discord.ButtonStyle.gray, disabled=True, custom_id="23")
    async def middle_button(self, interaction: discord.Interaction, button: Button):
        pass

    @discord.ui.button(label='>', style=discord.ButtonStyle.gray, custom_id="24")
    async def increase(self, interaction: discord.Interaction, button: Button):
        embed = interaction.message.embeds[0]
        embed_dict = {i.name: i.value for i in embed.fields}
        num = embed_dict["頁數"]
        url = embed.image.url
        title = embed.url
        id = extract_number_from_url(title)

        self.number = int(url[-10:-5])

        if self.number + 1 <= int(num):
            self.number += 1

        url = f"https://cdn-msp.18comic.org/media/photos/{id}/{fillnum(self.number)}.webp"

        self.middle_button.label = str(self.number) + "/" + num

        embed.set_image(url=self.domain+url)

        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.defer()
        channel = interaction.client.get_channel(config.JM_LOG_CHANNEL_ID)
        # await channel.send(f"{self.domain}{url}")

    @discord.ui.button(label='>>', style=discord.ButtonStyle.gray, custom_id="25")
    async def increasetoend(self, interaction: discord.Interaction, button: Button):
        embed = interaction.message.embeds[0]
        embed_dict = {i.name: i.value for i in embed.fields}
        num = embed_dict["頁數"]
        url = embed.image.url
        title = embed.url
        id = extract_number_from_url(title)

        self.number = int(num)
        self.middle_button.label = str(self.number)+"/"+num

        url = f"https://cdn-msp.18comic.org/media/photos/{id}/{fillnum(self.number)}.webp"

        embed.set_image(url=self.domain+url)

        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.defer()
        channel = interaction.client.get_channel(config.JM_LOG_CHANNEL_ID)
        # await channel.send(f"{self.domain}{url}")
        
if __name__ == "__main__":
    url = "https://18comic.vip/album/622529"
    print(jm_crawl(url))
