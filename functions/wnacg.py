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
import time
import aiohttp
from utils.ttl_cache import async_ttl_cache
from functions.cdn_pages import (apply_page as _apply_page, cdn_page_image, embed_thread_hint,
                                 total_pages as _total_pages, JumpModal, reply_with_edit,
                                 message_lock, edit_attachments)


AID_PATTERN = re.compile(r"aid-(\d+)\.html")
GALLERY_IMG_PATTERN = re.compile(r'url: fast_img_host\+\\"([^"\\]+)')


def cdn_gallery(digit):
    return f"wnacg-{digit}"


def cdn_key(digit, page_num):
    return f"wnacg-{digit}-{int(page_num)}"


WNACG_COLOR = 0x3498db


def apply_page(embed: discord.Embed, img, page_num, cdn=None, digit=None):
    _apply_page(embed, img, page_num, cdn, cdn_gallery(digit) if digit else None, colour=WNACG_COLOR)


@async_ttl_cache(ttl_seconds=1800, maxsize=128, key_arg="digit")
async def fetch_gallery_images(session: aiohttp.ClientSession, digit):
    """一次取得整本所有頁面的原圖網址（已帶 verify 參數）。
    photos-gallery-aid-*.html 是閱讀模式用的 JS，裡面的 imglist 列出每一頁；
    最後一筆是站方的收藏廣告圖（不在 /data/ 底下），要濾掉。"""
    url = f"https://www.wnacg.com/photos-gallery-aid-{digit}.html"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.61 Safari/537.36"}
    async with session.get(url, headers=headers) as response:
        response.raise_for_status()
        text = await response.text()
    images = []
    for src in GALLERY_IMG_PATTERN.findall(text):
        if "/data/" not in src:
            continue
        images.append("https:" + src if src.startswith("//") else src)
    if not images:
        raise RuntimeError(f"wnacg gallery {digit} has no images")
    return images


async def get_page_image(session: aiohttp.ClientSession, cdn, digit, page_num, page=None, thread_hint=None,
                         inline=False, first_src=None):
    """取得某一頁要放進 embed 的圖片網址：有圖床就是 Discord CDN 網址（並背景預載整本），
    沒有圖床或上傳失敗時退回原站網址。thread_hint 是 embed 上記錄的討論串 ID；
    first_src 是已經知道的該頁原圖網址（單頁連結），有的話不必先等整本清單。"""
    digit = str(digit)

    async def src_of(n):
        if first_src and n == int(page_num):
            return first_src
        try:
            return (await fetch_gallery_images(session, digit))[n - 1]
        except Exception as e:
            print(f"[wnacg] gallery list {digit} failed, fallback to view page: {e!r}", flush=True)
            return await find_img_new(session, digit, page, page_num=n)

    async def total():
        return len(await fetch_gallery_images(session, digit))

    url = await cdn_page_image(cdn, cdn_gallery(digit), page_num, src_of, total, thread_hint=thread_hint,
                               inline=inline)
    return url or await src_of(int(page_num))


async def wnacg_crawl(session: aiohttp.ClientSession, digit):
    """相簿資訊；同一本 30 分鐘內重貼不再重爬。失敗回傳 404（失敗結果不快取）。"""
    try:
        return await _wnacg_crawl_cached(session, str(digit))
    except Exception as e:
        print(f"Crawl error: {e}")
        return 404


@async_ttl_cache(ttl_seconds=1800, maxsize=256, key_arg="digit")
async def _wnacg_crawl_cached(session: aiohttp.ClientSession, digit):
    url = f"https://www.wnacg.com/photos-index-page-1-aid-{digit}.html"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.61 Safari/537.36"
    }

    async with session.get(url, headers=headers) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}")
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


async def create_wnacg_embed(session: aiohttp.ClientSession, digit, page_num=1, cdn=None, first_src=None):
    url = f"https://www.wnacg.com/photos-index-page-1-aid-{digit}.html"

    # 相簿資訊與目標頁圖片同時處理，圖床上傳不會疊加在爬蟲時間之後
    requested = max(1, int(page_num))
    image_task = asyncio.create_task(get_page_image(session, cdn, digit, requested, page=None, inline=True,
                                                    first_src=first_src))
    result = await wnacg_crawl(session, digit)
    if result == 404:
        image_task.cancel()
        return 404

    title, thumbnail, page, tag_lst, link = result

    # 防呆：確保跳轉的頁碼落在合法範圍內
    page_num = int(page_num)
    if page and page.isdigit():
        page_num = max(1, min(page_num, int(page)))

    embed = discord.Embed(title=title, url=url, color=WNACG_COLOR)
    embed.set_thumbnail(url=thumbnail)

    if page_num == requested:
        img = await image_task
    else:
        # 頁碼超出範圍被校正，改抓校正後的那一頁
        image_task.cancel()
        img = await get_page_image(session, cdn, digit, page_num, page=page, inline=True)

    apply_page(embed, img, page_num, cdn, digit)

    if tag_lst:
        embed.add_field(name="標籤", value=",".join(tag_lst))

    embed.add_field(name="頁數", value=page)
    embed.set_author(name="wnacg", icon_url="https://i.imgur.com/tZ3fqmm.jpeg")

    return embed


async def resolve_wnacg_view(session: aiohttp.ClientSession, view_id):
    """給定單頁瀏覽連結 (photos-view-id-*.html) 的 view id，反查其所屬相簿的
    aid、該頁的頁碼與原圖網址。view id 是每一頁各自獨立的編號，跟 aid 沒有規律可推算，
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

    # 這一頁本身就有帶 verify 的原圖網址，直接拿來上傳，不必等整本清單
    img = soup.find("img", {"id": "picarea"})
    img_src = img.get("src") if img else None
    if img_src and img_src.startswith("//"):
        img_src = "https:" + img_src

    return digit, page_num, img_src


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


async def render_wnacg_page(interaction: discord.Interaction, view, embed: discord.Embed, target):
    """翻頁、跳頁共用：取得目標頁圖片並更新 embed，回傳編輯訊息用的參數。
    舊版 embed（圖片是原站網址、沒有圖床索引）也會在這裡被升級成新格式。"""
    cdn = getattr(interaction.client, "image_cdn", None)
    digit = AID_PATTERN.search(embed.url).group(1)
    total = _total_pages(embed)
    target = max(1, int(target))
    if total:
        target = min(target, total)

    img = await get_page_image(view.session, cdn, digit, target, page=total,
                               thread_hint=embed_thread_hint(embed), inline=True)
    apply_page(embed, img, target, cdn, digit)

    view.number = target
    view._page_synced = True
    view.middle_button.label = f"{target}/{total}"
    # 這頁還沒上圖床就直接附在訊息上；否則清掉先前附在訊息上的圖
    return dict(embed=embed, view=view, attachments=edit_attachments(embed))


class NumberView2(View):
    def __init__(self, session: aiohttp.ClientSession, embed: discord.Embed = None):
        super().__init__(timeout=None)
        self.number = 1
        self.session = session
        self._page_synced = False

        if embed is not None:
            # embed 可能不是從第 1 頁開始（例如從 photos-view-id 連結建立），用 footer 校正
            self.number = get_current_page(embed)
            self._page_synced = True
            self.middle_button.label = f"{self.number}/{_total_pages(embed)}"

    # 頁碼一律讀這則訊息 embed 上的 footer：重開機後所有 wnacg 訊息共用 bot.py 註冊的
    # 同一個 View 實例，self.number 會被別則訊息改掉，不能拿來當目前頁。
    async def _go(self, interaction: discord.Interaction, target_of):
        embed = interaction.message.embeds[0]

        async def work():
            async with message_lock(interaction.message.id):
                current = get_current_page(embed)
                return await render_wnacg_page(interaction, self, embed, target_of(current, _total_pages(embed)))

        await reply_with_edit(interaction, work)

    @discord.ui.button(label='<<', style=discord.ButtonStyle.gray, custom_id="0000")
    async def decreasetostart(self, interaction: discord.Interaction, button: Button):
        await self._go(interaction, lambda current, total: 1)

    @discord.ui.button(label='<', style=discord.ButtonStyle.gray, custom_id="1111")
    async def decrease(self, interaction: discord.Interaction, button: Button):
        await self._go(interaction, lambda current, total: max(1, current - 1))

    @discord.ui.button(label="-", style=discord.ButtonStyle.primary, custom_id="2222")
    async def middle_button(self, interaction: discord.Interaction, button: Button):
        """中間按鈕：開啟跳頁視窗（custom_id 沿用舊版重新整理鈕，舊訊息也能用）。"""
        total = _total_pages(interaction.message.embeds[0])

        async def on_jump(modal_interaction, target):
            embed = modal_interaction.message.embeds[0]

            async def work():
                async with message_lock(modal_interaction.message.id):
                    return await render_wnacg_page(modal_interaction, self, embed, target)

            await reply_with_edit(modal_interaction, work)

        await interaction.response.send_modal(JumpModal(total, on_jump))

    @discord.ui.button(label='>', style=discord.ButtonStyle.gray, custom_id="3333")
    async def increase(self, interaction: discord.Interaction, button: Button):
        await self._go(interaction, lambda current, total: min(total or current + 1, current + 1))

    @discord.ui.button(label='>>', style=discord.ButtonStyle.gray, custom_id="4444")
    async def increasetoend(self, interaction: discord.Interaction, button: Button):
        await self._go(interaction, lambda current, total: total or current)


if __name__ == "__main__":
    import asyncio
    digit = "317161"

    async def main():
        async with aiohttp.ClientSession() as session:
            for page_num in (1, 2, 13):
                img = await find_img_new(session, digit, page="24", page_num=page_num)
                print(page_num, img)

    asyncio.run(main())