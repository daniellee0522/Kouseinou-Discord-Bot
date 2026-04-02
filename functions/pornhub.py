import aiohttp
from bs4 import BeautifulSoup
import re
import discord

async def get_pornhub_embed(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=10) as response:
                if response.status != 200:
                    return None
                html = await response.text()
        
        soup = BeautifulSoup(html, 'html.parser')

        # 1. 抓取資料 (使用更具魯棒性的選擇器或原有的)
        title_tag = soup.select_one('#hd-leftColVideoPage .title')
        title = title_tag.get_text(strip=True) if title_tag else "未知標題"

        thumbnail_tag = soup.select_one('#videoElementPoster')
        thumbnail_url = re.sub(r"\?cache=\d+", "", thumbnail_tag['src']) if thumbnail_tag else None

        rating_info_tag = soup.select_one('#hd-leftColVideoPage .videoInfo')
        upload_date = rating_info_tag.get_text(strip=True) if rating_info_tag else None

        views_tag = soup.select_one('.ratingInfo .views .count')
        views = views_tag.get_text(strip=True) if views_tag else None

        avatar_tag = soup.select_one('#hd-leftColVideoPage a.bolded')
        avatar_name = avatar_tag.get_text(strip=True) if avatar_tag else None

        image_tags = soup.select('#hd-leftColVideoPage img[loading="lazy"]')
        avatar_url = image_tags[1]['src'] if len(image_tags) > 1 else None

        category_tags = soup.select('a.gtm-event-video-underplayer.item')
        tags = [tag.get_text(strip=True) for tag in category_tags]

        # 2. 構建 Embed
        embed = discord.Embed(title=title, url=url, color=0xffa31a)
        embed.set_author(name="Pornhub", icon_url="https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTc4j-eWvLptAXrDbjnDavyGNA96HdBd9-fzQ&s")
        
        if thumbnail_url:
            embed.set_image(url=thumbnail_url)
        if avatar_url and avatar_name:
            embed.set_footer(text=avatar_name, icon_url=avatar_url)
        if views:
            embed.add_field(name='觀看數', value=views, inline=True)
        if upload_date:
            embed.add_field(name='上傳日期', value=upload_date, inline=True)
        if tags:
            embed.add_field(name='標籤', value=", ".join(tags[:10]), inline=False) # 限制標籤數量防止過長

        return embed

    except Exception as e:
        print(f"Pornhub Scraper Error: {e}")
        return None