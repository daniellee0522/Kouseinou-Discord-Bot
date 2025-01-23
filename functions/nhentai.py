import urllib.request as req
import bs4
import urllib.error
import discord
from discord.ui import Button, View
import re
import json


def nhentai_crawl(url, cf_clearance, csrftoken):
    r = req.Request(url, headers={
        "cookie": 'cf_clearance=' + cf_clearance + '; csrftoken=' + csrftoken + ';',
        "user-agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Mobile Safari/537.36"
    })

    try:
        with req.urlopen(r) as response:
            data = response.read().decode("utf-8")
        soup = bs4.BeautifulSoup(data, "html.parser")

    except urllib.error.HTTPError as e:
        if e.code == 404:
            return 404
        elif e.code == 403:
            return 403
    # print(soup)

    webdata = data
    # print(webdata)
    raws = re.search(r'JSON.parse.{2}({.+})', webdata).group(1)
    JsonData = json.loads(raws.encode('utf-8').decode('unicode-escape'))
    # print(JsonData)
    raw_strings = re.findall(
        r'data-src="(https?)://[A-z]+([0-9]+).{25,35}/(?:[0-9]+[A-z]+).([^"]+)', webdata)
    # print(raw_strings)
    link_lst = []
    for i, x in enumerate(raw_strings):
        link_lst.append("%s://i%s.nhentai.net/galleries/%s/%s.%s" % (
            x[0], x[1],JsonData['media_id'], i+1, x[2]))

    
    for i,url in enumerate(link_lst):
        if re.search(r'\.\w+\.\w+$', url):
            link_lst[i] = re.sub(r'\.(\w+)\.\w+$', r'.\1', url)
    link = link_lst[0]

    title = soup.select_one('meta[property="og:title"]').get('content')
    thumbnail = soup.select_one('meta[property="og:image"]').get('content')
    res = soup.find_all(
        'div', {"class": "tag-container field-name"})

    result = []
    for item in res:
        item_dict = {}
        tags = []
        header = item.contents[0].strip().rstrip(':')

        for tag in item.find_all('a', class_='tag'):
            tag_name = tag.find('span', class_='name').text
            tags.append(tag_name)
        if not tags:  # If there are no tags (e.g., for 'Uploaded')
            tags = [item.find('time').text] if item.find(
                'time') else []

        item_dict[header] = tags
        result.append(item_dict)
    return title, thumbnail, result, link, link_lst


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


def test_embed(digit, cf_clearance, csrftoken):
    url = add_url(digit)
    try:
        title, thumbnail, result, link, _ = nhentai_crawl(
            url, cf_clearance, csrftoken)
    except:
        error_code = nhentai_crawl(
            url, cf_clearance, csrftoken)
        return error_code
    embed = discord.Embed(title=title, url=url)
    embed.set_thumbnail(url=thumbnail)
    embed.set_image(
        url=link)
    # print(f"https://i3.nhentai.net/galleries/{digit}/1.jpg")
    for item in result:
        if "Artists" in item.keys():
            # print(item["Artists"])
            str_ = ""
            for i, author in enumerate(item["Artists"]):
                # print(author)
                if i+1 != len(item["Artists"]):
                    str_ += f"[{author}](https://nhentai.net/artist/{author.replace(' ','-')})"+","
                else:
                    str_ += f"[{author}](https://nhentai.net/artist/{author.replace(' ','-')})"
            embed.add_field(name="作者", value=str_)
        if "Tags" in item.keys():
            # print(item["Tags"])
            str_ = ""
            for i, tag in enumerate(item["Tags"]):
                if i+1 != len(item["Tags"]):
                    str_ += f"{tag}"+","
                else:
                    str_ += f"{tag}"
            embed.add_field(name="標籤", value=str_)
        if "Pages" in item.keys():
            # print("pages")
            embed.add_field(name="頁數", value=item["Pages"][0])
    embed.set_author(
        name="nhentai", icon_url="https://i.imgur.com/LslnmKV.png")
    return embed


class NumberView(View):
    def __init__(self,embed: discord.Embed = None):
        super().__init__(timeout=None)
        # self.message = message
        self.number = 1

        if embed != None:
            embed_dict = {i.name: i.value for i in embed.fields}
            num = embed_dict["頁數"]
            
            # 設置中間按鈕的標籤
            self.middle_button.label = f"{self.number}/{num}"
            
    @discord.ui.button(label='<<', style=discord.ButtonStyle.gray, custom_id="0")
    async def decreasetostart(self, interaction: discord.Interaction, button: Button):
        self.number = 1
        embed = interaction.message.embeds[0]
        embed_dict = {i.name: i.value for i in embed.fields}
        num = embed_dict["頁數"]
        url = embed.image.url
        title = embed.url

        _,_,_,_,link_lst = nhentai_crawl(title,"","")

        url = link_lst[0]

        embed.set_image(url=url)

        self.middle_button.label = str(self.number)+"/" + num

        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.defer()

    @discord.ui.button(label='<', style=discord.ButtonStyle.gray, custom_id="1")
    async def decrease(self, interaction: discord.Interaction, button: Button):
        embed = interaction.message.embeds[0]
        embed_dict = {i.name: i.value for i in embed.fields}
        num = embed_dict["頁數"]
        url = embed.image.url
        title = embed.url

        _,_,_,_,link_lst = nhentai_crawl(title,"","")

        pattern = r"/(\d+)\.(?:webp|jpg|jpeg|png|gif|bmp)$"
        self.number = int(re.search(pattern, url).group(1))
        if self.number > 1:
            self.number -= 1

        url = link_lst[self.number-1]

        embed.set_image(url=url)

        self.middle_button.label = str(self.number)+"/" + num

        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.defer()

    @discord.ui.button(label="-", style=discord.ButtonStyle.gray, disabled=True, custom_id="2")
    async def middle_button(self, interaction: discord.Interaction, button: Button):
        pass

    @discord.ui.button(label='>', style=discord.ButtonStyle.gray, custom_id="3")
    async def increase(self, interaction: discord.Interaction, button: Button):
        embed = interaction.message.embeds[0]
        embed_dict = {i.name: i.value for i in embed.fields}
        num = embed_dict["頁數"]
        url = embed.image.url
        title = embed.url

        _,_,_,_,link_lst = nhentai_crawl(title,"","")

        #print(url)
        pattern = r"/(\d+)\.(?:webp|jpg|jpeg|png|gif|bmp)$"
        self.number = int(re.search(pattern, url).group(1))

        if self.number + 1 <= int(num):
            self.number += 1

        url = link_lst[self.number-1]

        self.middle_button.label = str(self.number) + "/" + num

        embed.set_image(url=url)

        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.defer()

    @discord.ui.button(label='>>', style=discord.ButtonStyle.gray, custom_id="4")
    async def increasetoend(self, interaction: discord.Interaction, button: Button):
        embed = interaction.message.embeds[0]
        embed_dict = {i.name: i.value for i in embed.fields}
        num = embed_dict["頁數"]
        url = embed.image.url
        title = embed.url

        _,_,_,_,link_lst = nhentai_crawl(title,"","")

        self.number = int(num)
        self.middle_button.label = str(self.number)+"/"+num

        url = link_lst[self.number-1]

        embed.set_image(url=url)

        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.defer()
