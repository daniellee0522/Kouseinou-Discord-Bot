import asyncio
import requests
from bs4 import BeautifulSoup, NavigableString
import re
import discord
from requests_html import HTMLSession
from urllib.parse import urljoin, urlparse
from discord.ui import Button, View
import json
import os
import aiohttp


AID_PATTERN = re.compile(r"aid-(\d+)\.html")

async def wnacg_crawl(session: aiohttp.ClientSession, digit):
    url = f"https://www.wnacg.com/photos-index-page-1-aid-{digit}.html"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.61 Safari/537.36"
    }

    try:
        async with session.get(url, headers=headers) as response:
            if response.status != 200:
                return 404
            html = await response.text()
            soup = BeautifulSoup(html, 'html.parser')
            
            info = soup.find('div', {"class": "asTBcell uwconn"})
            title = soup.find("div", {"class": "userwrap"})
            
            # 簡化標題提取邏輯
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
            
            link_div = soup.find("div", {"class": "pic_box tb"})
            href = link_div.find('a').get('href')
            link = "https://www.wnacg.com/" + href

            # 提取縮圖
            if "//" not in soup.find_all('img')[2].get('src')[2:]:
                thumbnail = "https://" + soup.find_all('img')[2].get('src')[2:]
            else:
                thumbnail = "https:" + soup.find_all('img')[2].get('src')[2:]

            # 提取頁數與標籤
            page = "0"
            tag_lst = []
            info_text = info.get_text()
            if "頁數" in info_text:
                # 簡單正則提取數字
                page_match = re.search(r'頁數：(\d+)P', info_text)
                page = page_match.group(1) if page_match else "0"
            
            tags = info.find_all('a', href=re.compile(r"index-tag"))
            tag_lst = [t.get_text() for t in tags]

            return title, thumbnail, page, tag_lst, link
    except Exception as e:
        print(f"Crawl error: {e}")
        return 404


async def create_wnacg_embed(session: aiohttp.ClientSession, digit, page_num=1):
    url = f"https://www.wnacg.com/photos-index-page-1-aid-{digit}.html"

    # 呼叫異步版的爬蟲函數
    result = await wnacg_crawl(session, digit)
    if result == 404:
        return 404

    title, thumbnail, page, tag_lst, link = result

    # 防呆：確保跳轉的頁碼落在合法範圍內
    page_num = int(page_num)
    if page and page.isdigit():
        page_num = max(1, min(page_num, int(page)))

    embed = discord.Embed(title=title, url=url, color=0x3498db)
    embed.set_thumbnail(url=thumbnail)

    img = await find_img_new(session, digit, page, page_num=page_num)

    embed.set_image(url=img)
    embed.set_footer(text=str(page_num))  # 記錄目前頁碼，供翻頁按鈕讀取

    if tag_lst:
        embed.add_field(name="標籤", value=",".join(tag_lst))

    embed.add_field(name="頁數", value=page)
    embed.set_author(name="wnacg", icon_url="https://i.imgur.com/tZ3fqmm.jpeg")

    return embed


async def resolve_wnacg_view(session: aiohttp.ClientSession, view_id):
    """給定單頁瀏覽連結 (photos-view-id-*.html) 的 view id，反查其所屬相簿的
    aid 與該頁的頁碼。view id 是每一頁各自獨立的編號，跟 aid 沒有規律可推算，
    只能從頁面本身的麵包屑連結（找 aid）與頁碼標籤（找頁碼）反查。
    找不到（例如連結失效）時回傳 None。"""
    url = f"https://www.wnacg.com/photos-view-id-{view_id}.html"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.61 Safari/537.36"}

    async with session.get(url, headers=headers) as response:
        if response.status != 200:
            return None
        html = await response.text()

    soup = BeautifulSoup(html, 'html.parser')

    digit = None
    bread = soup.find("div", {"class": "png bread"})
    if bread:
        for a in bread.find_all('a'):
            aid_match = AID_PATTERN.search(a.get("href", ""))
            if aid_match:
                digit = aid_match.group(1)
                break
    if digit is None:
        return None

    page_label = soup.find("span", {"class": "newpagelabel"})
    page_num = int(page_label.find("b").text) if page_label else 1

    return digit, page_num


async def find_img_new(session: aiohttp.ClientSession, digit, page, page_num=1):
    """取得指定頁碼的原圖網址。

    網站現在要求原圖網址帶有有效的 ?verify=... 參數，該參數只能從單頁瀏覽頁面
    (photos-view-id-*.html) 取得，無法用縮圖網址規律推算。因此流程改為：
    1. 讀取縮圖列表頁，取得該頁對應的 photos-view-id 連結（原本就會抓這頁，未多一次爬蟲）
    2. 讀取該單頁瀏覽頁面，直接取出已附帶 verify 參數的原圖網址
    這樣每次翻頁仍是 2 次請求，與舊版（縮圖列表頁 + HEAD 驗證）的請求數相同。
    """
    index = (int(page_num) - 1) // 12 + 1
    local_idx = (int(page_num) - 1) % 12
    url = f"https://www.wnacg.com/photos-index-page-{index}-aid-{digit}.html"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.61 Safari/537.36"}

    async with session.get(url, headers=headers) as response:
        html = await response.text()
    soup = BeautifulSoup(html, 'html.parser')
    divs = soup.find_all("div", class_="pic_box tb")
    view_href = divs[local_idx].find('a').get('href')
    view_url = urljoin("https://www.wnacg.com/", view_href)

    async with session.get(view_url, headers=headers) as response:
        view_html = await response.text()
    view_soup = BeautifulSoup(view_html, 'html.parser')
    img_src = view_soup.find("img", {"id": "picarea"}).get("src")
    if img_src.startswith("//"):
        img_src = "https:" + img_src

    return img_src


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


def get_current_page(embed: discord.Embed) -> int:
    """讀取目前頁碼。頁碼記錄在 embed 的 footer；若是舊版訊息（頁碼記錄在圖片網址
    的 query string 中）則從那裡回退解析，避免舊訊息按按鈕時直接壞掉。"""
    footer_text = embed.footer.text if embed.footer else None
    if footer_text and footer_text.isdigit():
        return int(footer_text)

    try:
        parts = embed.image.url.split("?")
        legacy = parts[-2] if "TRUE" in parts[-1] else parts[-1]
        return int(legacy) if legacy.isdigit() else 1
    except (AttributeError, IndexError):
        return 1


class NumberView2(View):
    def __init__(self,session: aiohttp.ClientSession, embed:discord.Embed=None):
        super().__init__(timeout=None)
        # self.message = message
        self.number = 1
        self.session = session
        self.lock = asyncio.Lock()
        # 是否已經從訊息上的 embed 同步過目前頁碼；重開機後 View 會是全新的實例，
        # self.number 預設的 1 不可靠，第一次按按鈕時要用 get_current_page 校正一次。
        self._page_synced = False

        if embed != None:
            embed_dict = {i.name: i.value for i in embed.fields}
            num = embed_dict["頁數"]

            # embed 可能不是從第 1 頁開始（例如從 photos-view-id 連結建立），
            # 用 footer 記錄的頁碼校正，而不是寫死 1
            self.number = get_current_page(embed)
            self._page_synced = True

            # 設置中間按鈕的標籤
            self.middle_button.label = f"{self.number}/{num}"

    async def _edit_twice(self, interaction: discord.Interaction, embed: discord.Embed):
        # Discord 對「編輯訊息換上全新圖片網址」常常第一次抓不到圖(見
        # discord-api-docs#6540），要再編輯一次同樣內容才會正常顯示，
        # 這裡直接補一次相同的 edit 來規避。
        await interaction.message.edit(embed=embed, view=self)
        await asyncio.sleep(0.5)
        await interaction.message.edit(embed=embed, view=self)


    @discord.ui.button(label='<<', style=discord.ButtonStyle.gray, custom_id="0000")
    async def decreasetostart(self, interaction: discord.Interaction, button: Button):
        embed = interaction.message.embeds[0]
        digit = re.search(r"aid-(\d+)\.html", embed.url).group(1)

        for item in embed.fields:
            if item.name == "頁數":
                page = item.value

        await interaction.response.defer()

        async with self.lock:
            img = await find_img_new(self.session, digit=digit, page=page, page_num=1)

            embed.set_image(url=img)
            embed.set_footer(text="1")

            self.number = 1
            self._page_synced = True
            self.middle_button.label = f"1/{page}"

            await self._edit_twice(interaction, embed)

    @discord.ui.button(label='<', style=discord.ButtonStyle.gray, custom_id="1111")
    async def decrease(self, interaction: discord.Interaction, button: Button):
        embed = interaction.message.embeds[0]
        digit = re.search(r"aid-(\d+)\.html", embed.url).group(1)

        for item in embed.fields:
            if item.name == "頁數":
                page = item.value

        await interaction.response.defer()

        async with self.lock:
            self.number = get_current_page(embed)
            current = self.number
            num = current - 1 if current - 1 > 0 else current

            img = await find_img_new(self.session, digit=digit, page=page, page_num=num)

            embed.set_image(url=img)
            embed.set_footer(text=str(num))

            self.number = num
            self.middle_button.label = f"{num}/{page}"

            await self._edit_twice(interaction, embed)

    @discord.ui.button(label="-", emoji="🔄", style=discord.ButtonStyle.gray, custom_id="2222")
    async def middle_button(self, interaction: discord.Interaction, button: Button):
        """重新整理目前頁面：wnacg 的圖片網址帶有時效性的 verify 參數，
        大約一天左右就會過期；按這顆按鈕會重新爬取目前頁碼、換上新的有效連結。"""
        embed = interaction.message.embeds[0]
        digit = re.search(r"aid-(\d+)\.html", embed.url).group(1)

        for item in embed.fields:
            if item.name == "頁數":
                page = item.value

        await interaction.response.defer()

        async with self.lock:
            # 直接讀這則 embed 上記錄的頁碼，不能用 self.number：
            # 重開機後所有 wnacg 訊息共用 bot.py 註冊的同一個 View 實例，
            # self.number 會被別則訊息改掉，重整時就跳到別人的頁數。
            self.number = get_current_page(embed)
            current = self.number

            img = await find_img_new(self.session, digit=digit, page=page, page_num=current)

            embed.set_image(url=img)
            embed.set_footer(text=str(current))

            self.middle_button.label = f"{current}/{page}"

            await self._edit_twice(interaction, embed)

    @discord.ui.button(label='>', style=discord.ButtonStyle.gray, custom_id="3333")
    async def increase(self, interaction: discord.Interaction, button: Button):
        embed = interaction.message.embeds[0]
        digit = re.search(r"aid-(\d+)\.html", embed.url).group(1)

        for item in embed.fields:
            if item.name == "頁數":
                page = item.value

        await interaction.response.defer()

        async with self.lock:
            self.number = get_current_page(embed)
            current = self.number
            num = current + 1 if current + 1 <= int(page) else current

            img = await find_img_new(self.session, digit=digit, page=page, page_num=num)

            embed.set_image(url=img)
            embed.set_footer(text=str(num))

            self.number = num
            self.middle_button.label = f"{num}/{page}"

            await self._edit_twice(interaction, embed)

    @discord.ui.button(label='>>', style=discord.ButtonStyle.gray, custom_id="4444")
    async def increasetoend(self, interaction: discord.Interaction, button: Button):
        embed = interaction.message.embeds[0]
        digit = re.search(r"aid-(\d+)\.html", embed.url).group(1)

        for item in embed.fields:
            if item.name == "頁數":
                page = item.value

        await interaction.response.defer()

        async with self.lock:
            img = await find_img_new(self.session, digit=digit, page=page, page_num=page)

            embed.set_image(url=img)
            embed.set_footer(text=str(page))

            self.number = int(page)
            self._page_synced = True
            self.middle_button.label = f"{page}/{page}"

            await self._edit_twice(interaction, embed)


if __name__ == "__main__":
    import asyncio
    digit = "317161"

    async def main():
        async with aiohttp.ClientSession() as session:
            for page_num in (1, 2, 13):
                img = await find_img_new(session, digit, page="24", page_num=page_num)
                print(page_num, img)

    asyncio.run(main())