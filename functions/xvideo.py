import requests
from bs4 import BeautifulSoup
import re
import discord

# url = "https://www.xvideos.com/video.uffkhakaa77/_"  # 目標網站
headers = {"User-Agent": "Mozilla/5.0"}

def xvideo_embed(url):
    og_title = None
    og_image = None
    video_url = None
    views = None

    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    text = soup.prettify()

    ul = soup.select_one("#main > div.video-metadata.video-tags-list.ordered-label-list.cropped > ul")
    if ul:
        tags = [li.get_text() for li in ul.find_all("li")]
        tags.pop(-1)
        tags.pop(-1)
    else:
        tags = []

    og_title = soup.find("meta", property="og:title").get("content")
    og_image = soup.find("meta", property="og:image").get("content")
    video_url = re.search(r'html5player.setVideoUrlHigh\(\'(.*?)\'\)', text).group(1)
    views = soup.select_one("#v-views > strong.mobile-hide").get_text()

    if og_title:
        embed = discord.Embed(title=og_title, color=0xFFFFFF,url=url)
        embed.set_author(name="xvideo", icon_url="https://static-cdn77.xvideos-cdn.com/v3/img/skins/default/logo/xv.white.32.png")
        embed.set_thumbnail(url=og_image)
        if views:
            embed.add_field(name="觀看數", value=views) 
        if tags != []:
            embed.add_field(name="標籤", value=",".join(tags))

        return embed, video_url

if __name__ == "__main__":
    url = "https://www.xvideos.com/video.uffkhakaa77/_"
    pass

