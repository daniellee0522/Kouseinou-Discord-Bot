import discord
from discord.ext import commands
import re
import json
import asyncio
import random
from bs4 import BeautifulSoup
# 導入你原本在 functions 中的解析函數
from functions.embed_permission import is_embed_ban
from functions.slot import Gacha, check_lock, block_check
from functions.jm import jm_embed, NumberView3
from functions.xvideo import xvideo_embed
from functions.wnacg import create_wnacg_embed, NumberView2
from functions.nhentai import test_embed, NumberView
from functions.pornhub import get_pornhub_embed
from functions.supav import chrome_crawl, supjav_crawl
from functions.baha import extract_urls, bahaog, reload_baha_tk, Conf
from functions.gacha import process_gacha_data
import aiohttp
import config

# ... 其他解析函數
sac_bh = Conf('sacPY')

class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # 定義網址與對應處理函數的映射表 (範例)
        self.url_patterns = {
            r'18comic\.(?:vip|org)/album/(\d+)[^\s]*': self.handler_jm,
            r'wnacg(\.com|\.ru)/photos-(?:index|slide|slist|index-page|view)(?:-\d+)?-(?:aid|id)-(\d+)[^\s]*': self.handler_wnacg,
            r'nhentai\.net/g/(\d+)[^\s]*': self.handler_nhentai,
            r'missav\.(ai|ws)/(\w+)[^\s]*': self.handler_missav,
            r'jable\.tv/videos/([\w-]+)[^\s]*': self.handler_jable,
            r'xvideos\.com/video[^\s]*': self.handler_xvideo,
            r'pornhub\.com/view_video\.php\?viewkey=(\w+)': self.handler_pornhub,
            r"supjav.com\/[0-9]\+.html": self.handler_supjav,
            r'forum\.gamer\.com\.tw/.*?bsn=(\d+)[^\s]*': self.handler_baha,
        }
        self.keywords_match = {
            r"-1200": self.keyword_handler_gacha
        }

    def load_data(self,guild_id, num=1, DATA_FILE=None):
        if DATA_FILE is None:
            DATA_FILE = config.DATA_DIR / 'message_count.json'
        if guild_id in config.GUILD_IDS:
            return
        with open(DATA_FILE, "r") as f:
                data = json.load(f)
        if str(guild_id) not in data:
            data[str(guild_id)] = num
        else:
            data[str(guild_id)] += num
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=4)


    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        # 當 bot 加入新的伺服器時更新伺服器數量
        server_count = len(self.bot.guilds)

        # 更新 JSON 數據
        data = {
            "server_count": server_count
        }

        # load_data(guild.id, -1000)

        # 寫入 JSON 文件
        with open(config.DATA_DIR / 'server_count.json', 'w') as json_file:
            json.dump(data, json_file)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        # 當 bot 被踢出或退出伺服器時更新伺服器數量
        server_count = len(self.bot.guilds)

        # 更新 JSON 數據
        data = {
            "server_count": server_count
        }

        # 寫入 JSON 文件
        with open(config.DATA_DIR / 'server_count.json', 'w') as json_file:
            json.dump(data, json_file)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        server_id = str(member.guild.id)
        print("Somebody joined")
        # 替換為你的伺服器中的目標身分組名稱
        role_name = "新人"  
        # 獲取伺服器中的目標身分組
        role = discord.utils.get(member.guild.roles, name=role_name)
        if int(server_id) == 927850351703506954:
            try:
                # 為新成員分配身分組
                await member.add_roles(role)
                print(f"已成功為 {member.name} 分配身分組 {role.name}")
            except discord.Forbidden:
                print(f"無法分配身分組 {role.name}，請檢查權限")
            except discord.HTTPException as e:
                print(f"發生錯誤：{e}")
                
        with open(config.DATA_DIR / 'welcome.json', 'r', encoding='utf8') as file:
            data = json.load(file)
        if server_id in list(data.keys()):
            message = data[server_id][0]
            channel = self.bot.get_channel(data[server_id][1])
            await asyncio.sleep(1)
            await channel.send(message)
        else:
            name = member.guild.name
            await member.send(f"歡迎來到{name}伺服器")

    @commands.Cog.listener()
    async def on_message(self, message):
        process = False
        # 排除機器人自己的訊息
        if message.author.bot:
            return
        
        if block_check(message.channel.id):
            return
        
        for pattern, handler in self.url_patterns.items():
            matches = list(re.finditer(pattern, message.content))
            if matches:
                process = True
                for match in matches:
                    url = "https://" + match.group(0)
                    print(url)
                    # 執行處理函式
                    await handler(message, url, match)
        
        for pattern, handler in self.keywords_match.items():
            if pattern == message.content:
                await handler(message)
                process = True
                break

        await self.bot.process_commands(message)

        

    # --- 各個網址的處理邏輯 ---
    async def handler_jm(self, message, url, match):
        # await message.channel.send(f"偵測到 JM 網址: {url}")
        if is_embed_ban(server_id=message.channel.id, arg="jm"):
            return
        embed = await asyncio.to_thread(jm_embed, url)
        view = NumberView3(embed=embed)
        await message.channel.send(embed=embed, view=view)
        await message.edit(suppress=True) # 隱藏原網址預覽

    async def handler_wnacg(self, message, url, match):
        if is_embed_ban(server_id=message.channel.id, arg="wn"):
            return
        content_id = match.group(2)
        embed = await create_wnacg_embed(self.bot.session, content_id)
        view = NumberView2(session=self.bot.session, embed=embed)
        if embed not in [404, 403]:
            await message.channel.send(embed=embed, view=view)
            await message.edit(suppress=True)

    async def handler_nhentai(self, message, url, match):
        if is_embed_ban(server_id=message.channel.id, arg="nh"):
            return
        content_id = match.group(1)
        embed = await test_embed(session=self.bot.session, sec5h=self.bot.missav_crawl, digit=content_id, cf_clearance="", csrftoken="")
        view = NumberView(embed=embed)
        if embed:
            await message.channel.send(embed=embed, view=view)
            await message.edit(suppress=True)

    async def handler_xvideo(self, message, url, match):
        if is_embed_ban(server_id=message.channel.id, arg="andy"):
            return
        embed, video_url = await asyncio.to_thread(xvideo_embed, url)
        if embed:
            await message.channel.send(embed=embed)
            await message.channel.send(f"[.]({video_url})")
            await message.edit(suppress=True)

    async def handler_pornhub(self, message, url, match):
        embed = await get_pornhub_embed(url)
        if embed:
            await message.channel.send(embed=embed)
            await message.edit(suppress=True)

    async def handler_missav(self, message, url, match):
        response = await self.bot.missav_crawl.request(url)
        soup = BeautifulSoup(response, 'html.parser')
        description = soup.find('meta', attrs={'name': 'description'})
        title = soup.find('meta', attrs={'property': 'og:title'})
        image = soup.find('meta', attrs={'property': 'og:image'})

        embed = discord.Embed(title=title['content'], url=url)
        if image:
            embed.set_image(url=image['content'])
        if description:
            embed.description = description['content']

        embed.set_author(name="MissAV", url=url)

        await message.channel.send(embed=embed)
        await message.edit(suppress=True)

    async def handler_jable(self, message, url, match):
        response = await self.bot.jable_crawl.request(url)
        soup = BeautifulSoup(response, 'html.parser')
        title = soup.find('meta', attrs={'property': 'og:title'})
        image = soup.find('meta', attrs={'property': 'og:image'})

        embed = discord.Embed(title=title['content'], url=url)
        if image:
            embed.set_image(url=image['content'])

        embed.set_author(name="Jable", url=url)

        await message.channel.send(embed=embed)
        await message.edit(suppress=True)

    async def handler_supjav(self, message, url, match):
        embed = await supjav_crawl(url)
        if embed:
            await message.channel.send(embed=embed)
            await message.edit(suppress=True)

    async def handler_baha(self, message, url, match):
        # await message.channel.send(url)
        if is_embed_ban(server_id=message.channel.id, arg="baha"):
            return
        bsn = match.group(1)
        if bsn != "60076":
            return
        BAHAENUR = sac_bh.get('BAHAENUR')
        BAHARUNE = sac_bh.get('BAHARUNE')
        embed = bahaog(url=url, BAHAENUR=BAHAENUR, BAHARUNE=BAHARUNE, sac_bh=sac_bh)
        print(embed)
        await message.channel.send(embed=embed)
        await message.edit(suppress=True)

    async def keyword_handler_gacha(self, message):
        data, status = process_gacha_data(message.author.id, message.channel.id)
            
        if status == "lock": return
        if not data: return
            
            # 發送訊息
        await message.channel.send("<:B_env:1076108979375185930>\n<:Arona:1076109041136316496>")
        await message.channel.send("<:result:1076111748106571830>")
        await message.channel.send(data["feed"])
        await message.channel.send(data["stone"])
            
            # 特殊條件跳轉影片/圖
        res_list = data["result"]
        if 4 in res_list:
            await message.channel.send("https://cdn.discordapp.com/attachments/1149330986279108689/1171035321736110100/6bd4b9604ac8b986.mp4")
        if res_list.count(1) == 9 and res_list.count(2) == 1:
            await message.channel.send("https://cdn.discordapp.com/attachments/1040328234463666236/1080134411468689558/IMG_1177.jpg")


async def setup(bot):
    await bot.add_cog(Events(bot))