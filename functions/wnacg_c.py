import requests
from bs4 import BeautifulSoup, NavigableString
import re
import discord
from discord.ui import Button, View
import json
import logging
import os
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
from sec5sh import Sec5sh
import config

DATA_FILE = 'message_count.json'

def load_data(guild_id, num=1):
    if guild_id in config.GUILD_IDS:
        return
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
    if str(guild_id) not in data:
        data[str(guild_id)] = num
    else:
        data[str(guild_id)] += num
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

async def wnacg_crawl(digit, sec5sh=None):
    url = f"https://www.wnacg.com/photos-index-page-1-aid-{digit}.html"

    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.61 Safari/537.36"
    }

    response = requests.get(url, headers=headers)
    """
    # sec5sh = Sec5sh()
    response = await sec5sh.request(url)
    try:
        soup = BeautifulSoup(response, 'html.parser')
        # print(soup)
        info = soup.find('div', {"class": "asTBcell uwconn"})
        tag_lst = []
        title = soup.find("div", {"class": "userwrap"})
    except:
        return 404
    link = soup.find("div", {"class": "pic_box tb"})
    anchor_element = link.find('a')
    href = anchor_element.get('href')
    link = "https://www.wnacg.com/" + href
    # print(link)
    for item in title:
        if isinstance(item, NavigableString):
            if str(item) == "\n":
                continue
            else:
                title = str(item)
                break
        if item.text == "\n":
            continue
        else:
            title = item.text
            break
    # print(title)
    thumbnail = "https:" + soup.select_one("#bodywrap > div > div.asTBcell.uwthumb > img").get("src").replace("////","//")
    # print(thumbnail)
    for item in info:
        if "頁數" in str(item):
            page = str(item)[str(item).index("：")+1:str(item).index("P")]
        if "標籤" in str(item):
            for i, tag in enumerate(item):
                if i != 0 and "+TAG" not in str(tag) and "\n" not in str(tag):
                    tag_lst.append(tag.text)
        # print(item.text)
    # print(page)
    # print(tag_lst)

    # comics = soup.find_all("li", class_="gallary_item")

    return title, thumbnail, page, tag_lst, link


async def create_wnacg_embed(digit, sec5sh=None):
    url = f"https://www.wnacg.com/photos-index-page-1-aid-{digit}.html"
    try:
        title, thumbnail, page, tag_lst, link = await wnacg_crawl(
            digit=digit, sec5sh=sec5sh)
    except:
        error_code = await wnacg_crawl(
            digit=digit, sec5sh=sec5sh)
        return error_code
    embed = discord.Embed(title=title, url=url, color=0x3498db)
    embed.set_thumbnail(url=thumbnail)
    img = await find_img_new(digit=digit, page=page, page_num=1, sec5sh=sec5sh)
    # img = test_if_exist(img)
    img += "?TRUE"
    # print(img)
    embed.set_image(url=img)

    if tag_lst != []:
        str_ = ""
        for i, item in enumerate(tag_lst):
            if i+1 != len(tag_lst):
                str_ += item + ","
            else:
                str_ += item
        embed.add_field(name="標籤", value=str_)
    # embed.set_footer(text="1")
    embed.add_field(name="頁數", value=page)
    embed.set_author(
        name="wnacg", icon_url="https://i.imgur.com/tZ3fqmm.jpeg")
    return embed


async def find_img_new(digit, page, page_num=1,test=False, sec5sh=None):
    if sec5sh is None:
        sec5sh = Sec5sh()
    if int(page_num) % 12 == 0 and int(page_num) != 0:
        index = int(page_num) // 12
    else:
        index = int(page_num) // 12 + 1
    url = f"https://www.wnacg.com/photos-index-page-{index}-aid-{digit}.html"
    headers = { "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3" }
    response = await sec5sh.request(url)
    soup = BeautifulSoup(response, 'html.parser')


    # 找到所有 class="pic_box tb" 的 div
    divs = soup.find_all("div", class_="pic_box tb")

    name = soup.find_all("span", class_="name tb")
    name = [n.text for n in name]

    # 提取所有 img 標籤的 src 屬性
    img_urls = [img["src"] for div in divs for img in div.find_all("img")]
    print(img_urls[0])
    if "(" in name[0]:
        img_urls = ["https:" + url for url in img_urls]
    else:
        img_urls = ["https:" + re.sub(r'(?<=/)[^/.]+(?=\.[^.]+$)', names, urls) for names, urls in zip(name, img_urls)]
    print(img_urls[0])
    img_urls = [url + f"?{(i+1)+ (index-1)*12}" for i, url in enumerate(img_urls)]
    # print(img_urls[0])
    img_urls = [urls.replace("/t","/img",1) for urls in img_urls]
    # print(img_urls[0])
    img_urls = [urls.replace("t/","") for urls in img_urls]
    # print(img_urls[0])
    img_urls = [urls.replace("thumb/","") for urls in img_urls]

    # 輸出結果
    # print(name)
    img = img_urls[int(page_num)%12-1]

    if test:
        return img
    else:
        data = await test_if_exist(img)
        return data

async def test_if_exist(url):
    sec5sh = Sec5sh()
    headers = { "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3" }
    response = await sec5sh.read(url)
    if not response:
        print(f"Image not found: {url}")
        return re.sub(r'img(\d+)\.qy0\.ru', lambda m: f"img{int(m.group(1)) + 1}.qy0.ru", url)
    else:
        return url
    

def find_img(link, page):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.61 Safari/537.36"
    }
    response = requests.get(
        url=link,
        headers=headers,
    )
    soup = BeautifulSoup(response.content, 'html.parser')
    num = soup.find("span", {"class": "newpagelabel"}).find("b").text
    # print(soup)
    select = soup.find("select", {"class": "pageselect"})
    options = select.find_all('option')
    # print(select.text)
    table = str.maketrans("", "", "第頁")

    first_page_id = options[0]["value"]

    last_page_id = options[-1]["value"]

    if int(num) == 1:
        previous_id = first_page_id
        num_previous = num
    else:
        previous_id = options[int(num)-2]["value"]
        num_previous = str(int(num)-1)

    if num == page:
        next_id = last_page_id
        num_next = num
    else:
        next_id = options[int(num)]["value"]
        num_next = str(int(num)+1)

    img = soup.find_all("img", {"id": "picarea"})
    img = "https:" + img[0]["src"]

    return img, first_page_id, last_page_id, previous_id, next_id, num


def find_front_page(link):  # 專門找從單頁瀏覽找到首頁用的
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.61 Safari/537.36"
    }
    response = requests.get(
        url=link,
        headers=headers,
    )
    soup = BeautifulSoup(response.content, 'html.parser')
    item = soup.find("div", {"class": "png bread"})
    for i in item.find_all('a'):
        if "/photos-index-aid" in i["href"]:
            digit = i["href"].strip("/photos-index-aid-")[:-5]
            # print(digit)
            return digit

    return None


def replace_num_with_other(s1, s2):
    """將 s1 中的 num 替換為 s2 中的 num2"""
    match1 = re.search(r'img(\d+)\.qy0\.ru', s1)
    match2 = re.search(r'img(\d+)\.qy0\.ru', s2)
             
    if match1 and match2:
        num2 = match2.group(1)  # 從 s2 提取數字
        return re.sub(r'img\d+\.qy0\.ru', f"img{num2}.qy0.ru", s1)  # 替換 s1 中的數字
    return s1

class NumberView2(View):
    def __init__(self,embed:discord.Embed=None):
        super().__init__(timeout=None)
        # self.message = message
        self.number = 1
        self.s = Sec5sh()

        if embed != None:
            embed_dict = {i.name: i.value for i in embed.fields}
            num = embed_dict["頁數"]
            
            # 設置中間按鈕的標籤
            self.middle_button.label = f"{self.number}/{num}"
        

    @discord.ui.button(label='<<', style=discord.ButtonStyle.gray, custom_id="0000")
    async def decreasetostart(self, interaction: discord.Interaction, button: Button):
        test = False
        if interaction.guild:
            load_data(interaction.guild.id)

        embed = interaction.message.embeds[0]
        digit = re.search(r"aid-(\d+)\.html", embed.url).group(1)

        if "TRUE" in embed.image.url.split("?")[-1]:
            match1 = re.search(r'img(\d+)\.qy0\.ru', embed.image.url)
            test = True


        for item in embed.fields:
            if item.name == "頁數":
                page = item.value

        await interaction.response.defer()

        img = await find_img_new(digit, page, 1, test=test, sec5sh=self.s) + "?TRUE"
        if test:
            img = re.sub(r"img(\d+)\.qy0\.ru", match1.group(0), img)


        # img = test_if_exist(img)
        # img = replace_num_with_other(img, embed.image.url)

        embed.set_image(url=img)

        self.middle_button.label = f"1/{page}"

        await interaction.message.edit(embed=embed, view=self)
        # await interaction.response.defer()

    @discord.ui.button(label='<', style=discord.ButtonStyle.gray, custom_id="1111")
    async def decrease(self, interaction: discord.Interaction, button: Button):
        test = False
        if interaction.guild:
            load_data(interaction.guild.id)

        embed = interaction.message.embeds[0]
        digit = re.search(r"aid-(\d+)\.html", embed.url).group(1)

        if "TRUE" in embed.image.url.split("?")[-1]:
            match1 = re.search(r'img(\d+)\.qy0\.ru', embed.image.url)
            test = True
            page_num = embed.image.url.split("?")[-2]
        else:
            page_num = embed.image.url.split("?")[-1]
        num = int(page_num) - 1 if int(page_num) - 1 > 0 else int(page_num)

        for item in embed.fields:
            if item.name == "頁數":
                page = item.value

        await interaction.response.defer()
        img = await find_img_new(digit=digit, page=page, page_num=num,test=test, sec5sh=self.s) + "?TRUE"
        if test:
            img = re.sub(r"img(\d+)\.qy0\.ru", match1.group(0), img)
        # img = test_if_exist(img)
        # img = replace_num_with_other(img, embed.image.url)

        embed.set_image(url=img)

        self.middle_button.label = f"{num}/{page}"

        await interaction.message.edit(embed=embed, view=self)
        # await interaction.response.defer()

    @discord.ui.button(label="-", style=discord.ButtonStyle.gray, disabled=True, custom_id="2222")
    async def middle_button(self, interaction: discord.Interaction, button: Button):
        pass

    @discord.ui.button(label='>', style=discord.ButtonStyle.gray, custom_id="3333")
    async def increase(self, interaction: discord.Interaction, button: Button):
        test = False
        if interaction.guild:
            load_data(interaction.guild.id)

        embed = interaction.message.embeds[0]
        digit = re.search(r"aid-(\d+)\.html", embed.url).group(1)

        print(embed.image.url.split("?")[-1])
        logging.info(embed.image.url.split("?"))

        if "TRUE" in embed.image.url.split("?")[-1]:
            match1 = re.search(r'img(\d+)\.qy0\.ru', embed.image.url)
            test = True
            page_num = embed.image.url.split("?")[-2]
        else:
            page_num = embed.image.url.split("?")[-1]
        num = int(page_num) - 1 if int(page_num) - 1 > 0 else int(page_num)

        for item in embed.fields:
            if item.name == "頁數":
                page = item.value

        num = int(page_num) + 1 if int(page_num) + 1 <= int(page) else int(page_num)

        await interaction.response.defer()

        img = await find_img_new(digit, page, num, test=test, sec5sh=self.s) + "?TRUE"
        if test:
            img = re.sub(r"img(\d+)\.qy0\.ru", match1.group(0), img)
        # img = test_if_exist(img)
        # img = replace_num_with_other(img, embed.image.url)
        print(img)

        embed.set_image(url=img)

        self.middle_button.label = f"{num}/{page}"

        await interaction.message.edit(embed=embed, view=self)
        # await interaction.response.defer()

    @discord.ui.button(label='>>', style=discord.ButtonStyle.gray, custom_id="4444")
    async def increasetoend(self, interaction: discord.Interaction, button: Button):
        test = False
        if interaction.guild:
            load_data(interaction.guild.id)

        embed = interaction.message.embeds[0]

        digit = re.search(r"aid-(\d+)\.html", embed.url).group(1)
        if "TRUE" in embed.image.url.split("?")[-1]:
            match1 = re.search(r'img(\d+)\.qy0\.ru', embed.image.url)
            test = True
        # page_num = embed.image.url.split("?")[-1]

        for item in embed.fields:
            if item.name == "頁數":
                page = item.value

        await interaction.response.defer()

        img = await find_img_new(digit, page=page, page_num=page, test=test, sec5sh=self.s) + "?TRUE"
        if test:
            img = re.sub(r"img(\d+)\.qy0\.ru", match1.group(0), img)
        # img = test_if_exist(img)
        # img = replace_num_with_other(img, embed.image.url)

        embed.set_image(url=img)

        self.middle_button.label = f"{page}/{page}"

        await interaction.message.edit(embed=embed, view=self)
        # await interaction.response.defer()


if __name__ == "__main__":
    digit = "220055"
    async def test():
        test = await wnacg_crawl(digit, sec5sh=Sec5sh())
        print(test)
    asyncio.run(test())
    url = f"https://www.wnacg.com/photos-index-page-1-aid-{digit}.html"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    print(soup)
