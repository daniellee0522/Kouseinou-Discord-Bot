from bs4 import BeautifulSoup
import discord
from curl_cffi import requests
from discord.ui import Button, View
import re
import io
import sys
import os

your_cookie = os.environ.get("jm_cookie")

sys.stdout = io.TextIOWrapper(
    sys.stdout.buffer, encoding='utf-8')
public_headers = {
    'cookie': your_cookie,
    'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0"
}


def jm_crawl(url):
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
    soup = BeautifulSoup(html, 'lxml')
    title = soup.title.text
    try:
        title = title[:title.index("|")]
    except:
        pass
    # print(title)
    page = len(soup.find_all('select')[2].find_all('option'))
    # print(page)

    return title, page


def jm_embed(url):
    id = extract_number_from_url(url)
    url2 = f"https://18comic.vip/photo/{id}"
    title, page = jm_crawl(url2)
    embed = discord.Embed(title=title, url=url, color=0xe37e31)
    embed.set_author(
        name="禁漫天堂", icon_url="https://i.imgur.com/dYVERFN.png")
    embed.add_field(name="頁數", value=page)
    embed.set_thumbnail(url=f"https://enderdaniel.work/pic/transform?url=https://cdn-msp3.18comic.org/media/albums/{id}.jpg")
    url3= f"https://cdn-msp.18comic.vip/media/photos/{id}/00001.webp"

    # 該處裡的清單

    embed.set_image(url=f"https://enderdaniel.work/pic/transform?url={url3}")

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
        self.domain = f"https://enderdaniel.work/pic/transform?url="

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
        url = f"https://cdn-msp.18comic.vip/media/photos/{id}/00001.webp"
        


        embed.set_image(url= self.domain + url)

        self.middle_button.label = str(self.number)+"/" + num

        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.defer()
        channel = interaction.client.get_channel(1294356961202147439)
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

        url = f"https://cdn-msp.18comic.vip/media/photos/{id}/{fillnum(self.number)}.webp"

        embed.set_image(url=self.domain+url)

        self.middle_button.label = str(self.number)+"/" + num

        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.defer()
        channel = interaction.client.get_channel(1294356961202147439)
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

        url = f"https://cdn-msp.18comic.vip/media/photos/{id}/{fillnum(self.number)}.webp"

        self.middle_button.label = str(self.number) + "/" + num

        embed.set_image(url=self.domain+url)

        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.defer()
        channel = interaction.client.get_channel(1294356961202147439)
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

        url = f"https://cdn-msp.18comic.vip/media/photos/{id}/{fillnum(self.number)}.webp"

        embed.set_image(url=self.domain+url)

        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.defer()
        channel = interaction.client.get_channel(1294356961202147439)
        # await channel.send(f"{self.domain}{url}")
        
if __name__ == "__main__":
    # jm_embed(
    #    "https://18comic.vip/photo/642026/gsus-kita-nijika-s-part-time-job/")
    pass
