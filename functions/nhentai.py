import bs4
import discord
from discord.ui import Button, View
import re
import json
import requests
import random
import aiohttp
from pathlib import Path
import config

_NH_JSON = Path(__file__).parent.parent / 'data' / 'nh.json'

async def nhentai_crawl(session: aiohttp.ClientSession, sec5h, number="", cf_clearance="", csrftoken=""):
    url = f"https://nhentai.net/g/{number}/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
        "Referer": "https://nhentai.net/"
    }

    try:
        webdata = await sec5h.request(url)
    except Exception as e:
        async with session.get(url, headers=headers) as response:
            webdata = await response.text()
            
            # 判定是否被攔截：狀態碼不對 OR 包含 Cloudflare 特徵 OR 找不到關鍵 JSON
            is_blocked = (
                response.status != 200 or 
                "cf-browser-verification" in webdata or 
                "Just a moment..." in webdata or
                re.search(r'JSON.parse.{2}({.+})', webdata) is None # 重要：預先檢查正则
            )

            if is_blocked:
                print(f"[Debug] 偵測到攔截，請求 sec5h Docker...")
                # 這裡才會真正觸發 Docker 請求
                webdata = await sec5h.request(url)
        
    
    # 接下來才進行解析，確保 webdata 是正確的 HTML
    soup = bs4.BeautifulSoup(webdata, "html.parser")


    # 找到容器
    container = soup.find("div", class_="container", id="thumbnail-container")

    data_src_list = []
    if container:
        first_img = container.find("img", attrs={"src": True})
        if first_img:
            src = first_img["src"]
            match = re.search(r'/galleries/(\d+)/', src)
            if match:
                media_id = match.group(1)

        imgs = container.find_all("img", attrs={"src": True})
        for img in imgs:
            # 修正開頭的 // 為 https://
            src = img["src"]
            if src.startswith("//"):
                src = "https:" + src
            data_src_list.append(src)
    # print(data_src_list)
    for i,img in enumerate(data_src_list):


        # 把 t 改成 i
        img = img.replace("https://t", "https://i")

        # 移除檔名裡的 t，例如 8t.jpg → 8.jpg
        data_src_list[i] = re.sub(r'/(\d+)t(\.jpg|\.webp|\.png)', r'/\1\2', img)

        if re.search(r'\.\w+\.\w+$', img):
            data_src_list[i] = re.sub(r'\.(\w+)\.\w+$', r'.\1', data_src_list[i])

    
    
    link = data_src_list[0]
        

    title = soup.select_one('meta[property="og:title"]').get('content')

    if "https://" in soup.select_one('meta[property="og:image"]').get('content'):
        thumbnail = soup.select_one('meta[property="og:image"]').get('content')
    else:
        thumbnail = "https:" + soup.select_one('meta[property="og:image"]').get('content')

    res = soup.find_all(
        'div', {"class": "tag-container field-name"})

    result_data = {}
    tags_section = soup.find('section', id='tags')

    if tags_section:
        containers = tags_section.find_all('div', class_=lambda x: x and x.startswith('tag-container'))
        
        for container in containers:
            text_content = container.get_text(strip=True)
            if ":" in text_content:
                category_name = text_content.split(":")[0].strip()
                tag_names = []
                name_spans = container.find_all('span', class_=lambda x: x and x.startswith('name'))
                
                for span in name_spans:
                    tag_names.append(span.get_text(strip=True))
                
                if not tag_names:
                    value_text = text_content.split(":", 1)[1].strip()
                    result_data[category_name] = value_text
                else:
                    result_data[category_name] = tag_names

    # link_lst2 = [match_strip(link) for link in link_lst]
    # save_image_url(number, data_src_list, media_id)
    return title, thumbnail, result_data, link, data_src_list

def remove_query_string(url):
    # 使用正則表達式移除問號後面的部分
    if config.NH_PROXY_URL and config.NH_PROXY_URL in url:
        url = url.replace(f"{config.NH_PROXY_URL}?img=", "")
    return re.sub(r'\?[\d]+$', '', url)

def extract_numbers(url):
    pattern = re.compile(r'https://nhentai\.net/g/(\d+)(?:/(\d+))?/?')
    match = pattern.match(url)

    if match:
        number = match.group(1)
        page = match.group(2) if match.group(2) else None
        return number, page
    else:
        return None, None


def add_url(digit: str):
    url = "https://nhentai.net/g/" + digit + "/"
    return url


async def test_embed(session: aiohttp.ClientSession, sec5h, digit, cf_clearance, csrftoken, page=0):
    url = add_url(digit)
    try:
        title, thumbnail, result, link, link_list = await nhentai_crawl(session=session, sec5h=sec5h, number=digit, cf_clearance=cf_clearance, csrftoken=csrftoken)
    except:
        error_code = await nhentai_crawl(session=session, sec5h=sec5h, number=digit, cf_clearance=cf_clearance, csrftoken=csrftoken)
        return error_code
    embed = discord.Embed(title=title, url=url)
    embed.set_thumbnail(url=thumbnail)
    embed.set_image(
        url=link_list[page] if 0 <= page < len(link_list) else link)
    # print(f"https://i3.nhentai.net/galleries/{digit}/1.jpg")
    for key, value in result.items():
        if key == "Artists":
            # print(value)
            str_ = ""
            for i, author in enumerate(value):
                # print(author)
                if i+1 != len(value):
                    author2 = author.replace(' |', '')
                    str_ += f"[{author}](https://nhentai.net/artist/{author2.replace(' ','-')})"+","
                else:
                    author2 = author.replace(' |', '')
                    str_ += f"[{author}](https://nhentai.net/artist/{author2.replace(' ','-')})"
            embed.add_field(name="作者", value=str_)
        if key == "Tags":
            # print(value)
            str_ = ""
            for i, tag in enumerate(value):
                if i+1 != len(value):
                    str_ += f"{tag}"+","
                else:
                    str_ += f"{tag}"
            embed.add_field(name="標籤", value=str_)
        if key == "Pages":
            # print("pages")
            embed.add_field(name="頁數", value=value[0])
    embed.set_author(
        name="nhentai", icon_url="https://i.imgur.com/LslnmKV.png")
    return embed

def get_image_url(digit):
    with open(_NH_JSON, "r") as f:
        data = json.load(f)
    if str(digit) in data:
        link_lst = data[str(digit)]
        link_lst = [match_unstrip(link_lst[0], page-1, link) for page,link in enumerate(link_lst) if page != 0]

    return link_lst

def match_unstrip(digit, page, link):
    match = re.search(r'(\d+)_([a-z]+)$', link)
    if match:
        number = match.group(1)
        ext = match.group(2)
        return f"https://i{number}.nhentai.net/galleries/{digit}/{int(page)+1}.{ext}"

def save_image_url(digit, link_lst, media_id):
    with open(_NH_JSON, "r") as f:
        data = json.load(f)

    link_lst = [match_strip(link) for link in link_lst]
    link_lst.insert(0, media_id)
    data[str(digit)] = link_lst
    try:
        with open(_NH_JSON, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        data = {str(digit): link_lst}
        with open(_NH_JSON, "w") as f:
            json.dump(data, f, indent=4)


def match_strip(link):
    match = re.search(r'i(\d+)\..*\.(\w+)$', link)
    if match:
        number = match.group(1)
        ext = match.group(2)
        return f"{number}_{ext}"



class NumberView(View):
    def __init__(self,embed: discord.Embed = None, session: aiohttp.ClientSession = None, sec5h = None):
        super().__init__(timeout=None)
        # self.message = message
        self.number = 1
        self.session = session
        self.sec5h = sec5h

        if embed != None:
            embed_dict = {i.name: i.value for i in embed.fields}
            num = embed_dict["頁數"]
            
            # 設置中間按鈕的標籤
            self.middle_button.label = f"{self.number}/{num}"
            self.middle_button.disabled = True
            
    @discord.ui.button(label='<<', style=discord.ButtonStyle.gray, custom_id="0")
    async def decreasetostart(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        self.number = 1
        embed = interaction.message.embeds[0]
        embed_dict = {i.name: i.value for i in embed.fields}
        num = embed_dict["頁數"]
        url = embed.image.url
        # url = remove_query_string(url)
        title = embed.url
        number = extract_numbers(title)[0]

        new_embed = await test_embed(session=self.session, sec5h=self.sec5h, digit=number, cf_clearance="", csrftoken="", page=self.number-1)
        # link_lst = get_image_url(number)
        # link_lst = [match_unstrip(number, page, link) for page,link in enumerate(link_lst)]

        # url = link_lst[0]

        # embed.set_image(url=url)

        self.middle_button.label = str(self.number)+"/" + num

        await interaction.message.edit(embed=new_embed, view=self)
        # await interaction.response.defer()

    @discord.ui.button(label='<', style=discord.ButtonStyle.gray, custom_id="1")
    async def decrease(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        embed = interaction.message.embeds[0]
        embed_dict = {i.name: i.value for i in embed.fields}
        num = embed_dict["頁數"]
        url = embed.image.url
        # url = remove_query_string(url)
        title = embed.url
        number = extract_numbers(title)[0]

        
        # link_lst = get_image_url(number)
        # link_lst = [match_unstrip(number, page, link) for page,link in enumerate(link_lst)]

        pattern = r"/(\d+)\.(?:webp|jpg|jpeg|png|gif|bmp)$"
        self.number = int(re.search(pattern, url).group(1))
        if self.number > 1:
            self.number -= 1

        new_embed = await test_embed(session=self.session, sec5h=self.sec5h, digit=number, cf_clearance="", csrftoken="", page=self.number-1)

        # url = link_lst[self.number-1]
        # embed.set_image(url=url)

        self.middle_button.label = str(self.number)+"/" + num

        await interaction.message.edit(embed=new_embed, view=self)
        # await interaction.response.defer()

    @discord.ui.button(label="-", style=discord.ButtonStyle.gray, disabled=True, custom_id="2")
    async def middle_button(self, interaction: discord.Interaction, button: Button):
        embed = interaction.message.embeds[0]
        url = embed.image.url
        # url = remove_query_string(url)
        url = url + "?" + str(random.randint(1, 1000))
        embed.set_image(url=url)
        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(label='>', style=discord.ButtonStyle.gray, custom_id="3")
    async def increase(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        embed = interaction.message.embeds[0]
        embed_dict = {i.name: i.value for i in embed.fields}
        num = embed_dict["頁數"]
        url = embed.image.url
        # url = remove_query_string(url)
        title = embed.url
        number = extract_numbers(title)[0]

        
        # _,_,_,_,link_lst = await nhentai_crawl(session=self.session, sec5h=self.sec5h, number=number, cf_clearance="", csrftoken="")
        # link_lst = get_image_url(number)
        # link_lst = [match_unstrip(number, page, link) for page,link in enumerate(link_lst)]

        #print(url)
        pattern = r"/(\d+)\.(?:webp|jpg|jpeg|png|gif|bmp)$"
        self.number = int(re.search(pattern, url).group(1))

        if self.number + 1 <= int(num):
            self.number += 1

        new_embed = await test_embed(session=self.session, sec5h=self.sec5h, digit=number, cf_clearance="", csrftoken="", page=self.number-1)
        # url = link_lst[self.number-1]

        self.middle_button.label = str(self.number) + "/" + num

        # embed.set_image(url=url)

        # logging.info(f"url: {url}")

        await interaction.message.edit(embed=new_embed, view=self)
        # await interaction.response.defer()

    @discord.ui.button(label='>>', style=discord.ButtonStyle.gray, custom_id="4")
    async def increasetoend(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        embed = interaction.message.embeds[0]
        embed_dict = {i.name: i.value for i in embed.fields}
        num = embed_dict["頁數"]
        url = embed.image.url
        # url = remove_query_string(url)
        title = embed.url
        number = extract_numbers(title)[0]

        
        # _,_,_,_,link_lst = await nhentai_crawl(session=self.session, sec5h=self.sec5h, number=number, cf_clearance="", csrftoken="")
        # link_lst = get_image_url(number)
        # link_lst = [match_unstrip(number, page, link) for page,link in enumerate(link_lst)]

        self.number = int(num)
        self.middle_button.label = str(self.number)+"/"+num

        new_embed = await test_embed(session=self.session, sec5h=self.sec5h, digit=number, cf_clearance="", csrftoken="", page=self.number-1)

        # url = link_lst[self.number-1]
        # embed.set_image(url=url)

        await interaction.message.edit(embed=new_embed, view=self)
        # await interaction.response.defer()


async def main():
    sec5h = Sec5sh()
    number = "549984"
    url = "https://nhentai.net/g/650154/"
    webdata = await sec5h.request(url)
    soup = bs4.BeautifulSoup(webdata, "html.parser")
    result_data = {}
    tags_section = soup.find('section', id='tags')

    if tags_section:
        # 2. 找出裡面所有的標籤容器（每一個 div 代表一個分類，如 Parodies、Tags）
        # 這裡使用 class^="tag-container" 代表「只要 class 開頭是 tag-container 即可」
        
        containers = tags_section.find_all('div', class_=lambda x: x and x.startswith('tag-container'))
        
        for container in containers:
            # 取得這一行的文字內容（例如: "Parodies: original 140.5k"）
            text_content = container.get_text(strip=True)
            
            # 用冒號 ":" 切割，前面就是分類名稱（如 Parodies、Tags、Pages 等）
            if ":" in text_content:
                category_name = text_content.split(":")[0].strip()
                
                # --- 情況 A：如果是普通的標籤分類（裡面有很多 tagchip） ---
                # 我們要精準抓取 <span class="name"> 裡面的純標籤文字，把後面的數量（140.5k）剃除
                tag_names = []
                # 尋找所有 class 開頭是 name 的 span 標籤
                name_spans = container.find_all('span', class_=lambda x: x and x.startswith('name'))
                
                for span in name_spans:
                    tag_names.append(span.get_text(strip=True))
                
                # --- 情況 B：如果是頁數（Pages）或時間（Uploaded）等特殊欄位 ---
                # 如果發現找不到任何 tagchip 的 name，代表它是單純的文字或數字
                if not tag_names:
                    # 取得冒號後面的剩餘所有文字作為值
                    value_text = text_content.split(":", 1)[1].strip()
                    result_data[category_name] = value_text
                else:
                    # 正常將分類與解析好的標籤清單存入字典
                    result_data[category_name] = tag_names
    print(result_data)

if __name__ == "__main__":
    # Create the session inside the running event loop
    import os
    import sys

    # 自動取得 nhentai.py 所在的資料夾路徑，並加入 Python 搜尋清單中
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.append(current_dir)
    from sec5sh import Sec5sh

    import asyncio
    asyncio.run(main())