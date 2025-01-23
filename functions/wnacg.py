import requests
from bs4 import BeautifulSoup, NavigableString
import discord
from urllib.parse import urljoin, urlparse
from discord.ui import Button, View


def wnacg_crawl(digit):
    url = f"https://www.wnacg.com/photos-index-page-1-aid-{digit}.html"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.61 Safari/537.36"
    }

    response = requests.get(url, headers=headers)
    try:
        soup = BeautifulSoup(response.content, 'html.parser')
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
    if "//" not in soup.find_all('img')[1].get('src')[2:]:
        thumbnail = "https://" + soup.find_all('img')[1].get('src')[2:]
    else:
        thumbnail = "https:" + soup.find_all('img')[1].get('src')[2:]
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


def create_wnacg_embed(digit):
    url = f"https://www.wnacg.com/photos-index-page-1-aid-{digit}.html"
    try:
        title, thumbnail, page, tag_lst, link = wnacg_crawl(
            digit=digit)
    except:
        error_code = wnacg_crawl(
            digit=digit)
        return error_code
    embed = discord.Embed(title=title, url=url, color=0x3498db)
    embed.set_thumbnail(url=thumbnail)
    img, _, _, _, _, _ = find_img(link=link, page=page)
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
    embed.set_footer(text=link)
    embed.add_field(name="頁數", value=page)
    embed.set_author(
        name="wnacg", icon_url="https://i.imgur.com/tZ3fqmm.jpeg")
    return embed


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


class NumberView2(View):
    def __init__(self,embed:discord.Embed=None):
        super().__init__(timeout=None)
        # self.message = message
        self.number = 1

        if embed != None:
            embed_dict = {i.name: i.value for i in embed.fields}
            num = embed_dict["頁數"]
            
            # 設置中間按鈕的標籤
            self.middle_button.label = f"{self.number}/{num}"
        

    @discord.ui.button(label='<<', style=discord.ButtonStyle.gray, custom_id="0000")
    async def decreasetostart(self, interaction: discord.Interaction, button: Button):
        embed = interaction.message.embeds[0]
        link = embed.footer.text
        for item in embed.fields:
            if item.name == "頁數":
                page = item.value
        _, id, _, _, _, _ = find_img(link, page=page)
        img, _, _, _, _, num = find_img(
            f"https://www.wnacg.com//photos-view-id-{id}.html", page)
        embed.set_footer(
            text=f"https://www.wnacg.com//photos-view-id-{id}.html")
        embed.set_image(url=img)

        self.middle_button.label = f"{num}/{page}"

        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.defer()

    @discord.ui.button(label='<', style=discord.ButtonStyle.gray, custom_id="1111")
    async def decrease(self, interaction: discord.Interaction, button: Button):
        embed = interaction.message.embeds[0]
        link = embed.footer.text
        for item in embed.fields:
            if item.name == "頁數":
                page = item.value
        _, _, _, id, _, _ = find_img(link, page=page)
        img, _, _, _, _, num = find_img(
            f"https://www.wnacg.com//photos-view-id-{id}.html", page)

        embed.set_image(url=img)
        embed.set_footer(
            text=f"https://www.wnacg.com//photos-view-id-{id}.html")

        self.middle_button.label = f"{num}/{page}"

        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.defer()

    @discord.ui.button(label="-", style=discord.ButtonStyle.gray, disabled=True, custom_id="2222")
    async def middle_button(self, interaction: discord.Interaction, button: Button):
        pass

    @discord.ui.button(label='>', style=discord.ButtonStyle.gray, custom_id="3333")
    async def increase(self, interaction: discord.Interaction, button: Button):
        embed = interaction.message.embeds[0]
        link = embed.footer.text
        for item in embed.fields:
            if item.name == "頁數":
                page = item.value
        _, _, _, _, id, _ = find_img(link, page=page)
        img, _, _, _, _, num = find_img(
            f"https://www.wnacg.com//photos-view-id-{id}.html", page)
        embed.set_footer(
            text=f"https://www.wnacg.com//photos-view-id-{id}.html")
        embed.set_image(url=img)

        self.middle_button.label = f"{num}/{page}"

        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.defer()

    @discord.ui.button(label='>>', style=discord.ButtonStyle.gray, custom_id="4444")
    async def increasetoend(self, interaction: discord.Interaction, button: Button):
        embed = interaction.message.embeds[0]
        link = embed.footer.text
        for item in embed.fields:
            if item.name == "頁數":
                page = item.value
        _, _, id, _, _, _ = find_img(link, page=page)
        img, _, _, _, _, num = find_img(
            f"https://www.wnacg.com//photos-view-id-{id}.html", page)
        embed.set_footer(
            text=f"https://www.wnacg.com//photos-view-id-{id}.html")
        embed.set_image(url=img)

        self.middle_button.label = f"{num}/{page}"

        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.defer()

# img, _, _, _, _ = find_img(
#    "https://www.wnacg.com//photos-view-id-21339313.html", "14")
# print(img)
# wnacg_crawl(258525)


# find_front_page("https://www.wnacg.com/photos-view-id-21369037.html")
