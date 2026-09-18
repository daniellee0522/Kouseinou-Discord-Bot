import asyncio
from bs4 import BeautifulSoup
import discord
from curl_cffi import requests
from discord.ui import Button, View
import re
import io
import sys

sys.path.append(r"./")
import config

sys.stdout = io.TextIOWrapper(
    sys.stdout.buffer, encoding='utf-8')



FLARESOLVERR_URL = "http://localhost:8191/v1"

_DIRECT_HEADERS = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,'
              'application/signed-exchange;v=b3;q=0.7',
    'accept-language': 'zh-TW,zh;q=0.9',
}


def _parse_jm_page(html, url):
    """解析頁面 HTML，取不到頁數（通常代表被 Cloudflare 擋下）時回傳 None。"""
    soup = BeautifulSoup(html, 'lxml')

    title = soup.title.text if soup.title else ""
    try:
        title = title[:title.index("|")]
    except ValueError:
        pass

    album_id = extract_number_from_url(url)
    if album_id is None:
        pattern = re.compile(r'/album/(\d+)/')
        for script in soup.find_all("script"):
            if script.string:
                match = pattern.search(script.string)
                if match:
                    album_id = match.group(1)
                    break

    pagecount_span = soup.find("span", class_="pagecount")
    if not pagecount_span:
        return None
    page_count = int(re.search(r"\d+", pagecount_span.get_text()).group())

    return title, page_count, album_id


def jm_crawl(url):
    # 先用有偽裝 TLS 指紋的直接請求，速度快、多數時候就能過 Cloudflare
    try:
        request = requests.get(url, headers=_DIRECT_HEADERS, impersonate="chrome124", timeout=15)
        result = _parse_jm_page(request.text, url)
        if result:
            return result
    except Exception:
        pass

    # Cloudflare 加強阻擋時，直接請求會被擋下(沒有 pagecount 或直接失敗)，
    # 改交給本機的 FlareSolverr（會開無頭瀏覽器真的解 JS challenge）再試一次
    payload = {
        "cmd": "request.get",
        "url": url,
        "maxTimeout": 60000,
    }
    response = requests.post(FLARESOLVERR_URL, json=payload, timeout=65).json()
    if response.get("status") != "ok":
        raise RuntimeError(f"FlareSolverr 解析失敗：{response.get('message')}")
    html = response["solution"]["response"]

    result = _parse_jm_page(html, url)
    if not result:
        raise RuntimeError("JM 頁面解析失敗（FlareSolverr 也無法取得頁數資訊），可能是頁面結構已變更")
    return result


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

def extract_page_number(url: str) -> int:
    from urllib.parse import unquote
    url_decoded = unquote(url)
    match = re.search(r'/(\d{5})\.webp', url_decoded)
    if match:
        return int(match.group(1))
    return 1


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


class NumberView3(discord.ui.View):
    def __init__(self, embed: discord.Embed = None):
        super().__init__(timeout=None)
        self.number = 1
        self.domain = f"{config.PIC_PROXY_URL}/transform?url="
        self.lock = asyncio.Lock()
        # 舊訊息共用 persistent View，每次操作都從該訊息讀取頁碼。
        if embed is not None:
            embed_dict = {i.name: i.value for i in embed.fields}
            num = embed_dict["頁數"]
            self.middle_button.label = f"{self.number}/{num}"

    def _sync_number(self, embed: discord.Embed):
        self.number = extract_page_number(embed.image.url)

    async def _edit_twice(self, interaction: discord.Interaction, embed: discord.Embed):
        # Discord 對「編輯訊息換上全新圖片網址」常常第一次抓不到圖(見
        # discord-api-docs#6540），要再編輯一次同樣內容才會正常顯示，
        # 這裡直接補一次相同的 edit 來規避。
        await interaction.message.edit(embed=embed, view=self)
        await asyncio.sleep(0.9)
        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(label='<<', style=discord.ButtonStyle.gray, custom_id="21")
    async def decreasetostart(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        embed = interaction.message.embeds[0]
        embed_dict = {i.name: i.value for i in embed.fields}
        num = embed_dict["頁數"]
        title = embed.url
        id = extract_number_from_url(title)

        async with self.lock:
            self.number = 1
            url = f"https://cdn-msp.18comic.org/media/photos/{id}/{fillnum(self.number)}.webp"
            embed.set_image(url=self.domain + url)
            self.middle_button.label = f"{self.number}/{num}"
            await self._edit_twice(interaction, embed)

    @discord.ui.button(label='<', style=discord.ButtonStyle.gray, custom_id="22")
    async def decrease(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        embed = interaction.message.embeds[0]
        embed_dict = {i.name: i.value for i in embed.fields}
        num = embed_dict["頁數"]
        title = embed.url
        id = extract_number_from_url(title)

        async with self.lock:
            self._sync_number(embed)
            if self.number > 1:
                self.number -= 1
            url = f"https://cdn-msp.18comic.org/media/photos/{id}/{fillnum(self.number)}.webp"
            embed.set_image(url=self.domain + url)
            self.middle_button.label = f"{self.number}/{num}"
            await self._edit_twice(interaction, embed)

    @discord.ui.button(label="-", style=discord.ButtonStyle.gray, disabled=True, custom_id="23")
    async def middle_button(self, interaction: discord.Interaction, button: Button):
        pass

    @discord.ui.button(label='>', style=discord.ButtonStyle.gray, custom_id="24")
    async def increase(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        embed = interaction.message.embeds[0]
        embed_dict = {i.name: i.value for i in embed.fields}
        num = embed_dict["頁數"]
        title = embed.url
        id = extract_number_from_url(title)

        async with self.lock:
            self._sync_number(embed)
            if self.number + 1 <= int(num):
                self.number += 1
            url = f"https://cdn-msp.18comic.org/media/photos/{id}/{fillnum(self.number)}.webp"
            embed.set_image(url=self.domain + url)
            self.middle_button.label = f"{self.number}/{num}"
            await self._edit_twice(interaction, embed)

    @discord.ui.button(label='>>', style=discord.ButtonStyle.gray, custom_id="25")
    async def increasetoend(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        embed = interaction.message.embeds[0]
        embed_dict = {i.name: i.value for i in embed.fields}
        num = embed_dict["頁數"]
        title = embed.url
        id = extract_number_from_url(title)

        async with self.lock:
            self.number = int(num)
            url = f"https://cdn-msp.18comic.org/media/photos/{id}/{fillnum(self.number)}.webp"
            embed.set_image(url=self.domain + url)
            self.middle_button.label = f"{self.number}/{num}"
            await self._edit_twice(interaction, embed)

if __name__ == "__main__":
    url = "https://18comic.vip/album/622529"
    print(jm_crawl(url))
