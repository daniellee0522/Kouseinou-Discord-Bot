import json
import asyncio
import os
import discord
import logging
from pathlib import Path
from discord.ext import commands
from functions.sec5sh import Sec5sh
from functions.baha import Conf, reload_baha_tk
from functions.nhentai import NumberView
from functions.wnacg import NumberView2
import aiohttp
from functions.jm import NumberView3
from functions.kemono import KemonoView
from functions.hitomi import HitomiView
from functions.ehentai import EHentaiView
from functions.discord_cdn import DiscordImageCDN
import config

os.chdir(Path(__file__).parent)  # 將工作目錄切換到腳本所在的目錄
logging.basicConfig(level=logging.INFO)

class MyBot(commands.Bot):
    def __init__(self):
        # 初始化 Intents
        intents = discord.Intents.default()
        intents.members = True
        intents.messages=True
        intents.message_content = True
        intents.guilds=True
        intents.presences = False

        # 呼叫父類別建構子
        super().__init__(
            command_prefix='$',
            intents=intents,
            help_command=None,
            # 不在啟動時逐一抓取每個伺服器的成員：伺服器超過約 110 個時，
            # 啟動瞬間的成員請求會撞到 gateway 送出上限（60 秒約 110 次），卡住約一分鐘才 ready。
            # on_member_join 等成員事件不受影響。
            chunk_guilds_at_startup=False,
        )
        self.session = None

        # 將原本的全域變數封裝為屬性 (Attributes)
        self.sac_bh = Conf('sacPY')
        self.missav_crawl = Sec5sh()
        self.jable_crawl = Sec5sh()
        self.supjav_crawl = Sec5sh()
        self.mobile01_crawl = Sec5sh()
        self.hanime_crawl = Sec5sh()
        self.iwara_crawl = Sec5sh()
        self.x_lst = {}
        self.data_lock = asyncio.Lock() # 避免與內建屬性 lock 衝突

        # 初始化邏輯
        reload_baha_tk(self.sac_bh)

    async def setup_hook(self):
        """這是在機器人啟動前會執行的異步初始化函數"""
        self.session = aiohttp.ClientSession()
        self.image_cdn = DiscordImageCDN(self, config.IMAGE_CDN_CHANNEL_ID)
        # 載入所有 Cog
        for filename in os.listdir('./cmds'):
            if filename.endswith('.py'):
                try:
                    await self.load_extension(f'cmds.{filename[:-3]}')
                    print(f"Loaded extension: {filename}")
                except Exception as e:
                    print(f"Failed to load extension {filename}: {e}")

    async def close(self):
        # 關閉機器人時同時關閉 Session，避免記憶體洩漏
        if self.session:
            await self.session.close()
        await self.image_cdn.close()
        await super().close()

    async def on_ready(self):
        self.add_view(NumberView(session=self.session, sec5h=self.missav_crawl))
        self.add_view(NumberView2(session=self.session))
        self.add_view(NumberView3())
        self.add_view(KemonoView(session=self.session))
        self.add_view(HitomiView(session=self.session))
        self.add_view(EHentaiView(session=self.session))
        self.image_cdn.start()  # 掃描圖床頻道既有的討論串，重建本子 → 討論串的對應

        server_count = len(self.guilds)
        data = {
            "server_count": server_count
        }

        # 寫入 JSON 文件
        with open('server_count.json', 'w') as json_file:
            json.dump(data, json_file)

        print(f'>> {self.user.name} is online <<')
        
        await self.change_presence(activity=discord.Game("ATRI -My Dear Moments-"))
        
        try:
            synced = await self.tree.sync()
            print(f'Synced {len(synced)} commands.')
        except Exception as e:
            print(f'Failed to sync commands: {e}')


async def main():
    with open('data/token.json', 'r', encoding='utf8') as file:
        config = json.load(file)

    bot = MyBot()
    
    async with bot:
        await bot.start(config["token"])

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot is shutting down...")