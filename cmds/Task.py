import json
import asyncio
import datetime
import pytz
import discord
import logging
from functions.ani_gamer import poll_updates, next_poll_delay
from core.classes import Cog_Extension
import config

logging.basicConfig(level=logging.ERROR, format='%(asctime)s %(levelname)s:%(message)s')

# 平常每隔多久抓一次動畫瘋首頁（秒）。不依賴播出時間，所以延遲上架、改期都能抓到
POLL_INTERVAL = 180
# 訂閱的動畫在播出時段內還沒更新時，改成每隔多久抓一次（秒）
FAST_POLL_INTERVAL = 10


def build_update_embed(update):
    embed = discord.Embed(
        title=update["name"]+"更新到"+update["episode"]+"了!",
        description="觀看網址:\n"+update["href"],
        color=0x5568, timestamp=datetime.datetime.now(pytz.utc)
    )
    embed.set_author(name="巴哈姆特動畫瘋", icon_url="https://i.imgur.com/RF7sMkY.png")
    if update["image"]:
        embed.set_image(url=update["image"])
    return embed


class Task(Cog_Extension):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._task = self.bot.loop.create_task(self.time_task())

    def cog_unload(self):
        self._task.cancel()

    async def time_task(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                notifications, removed = await asyncio.to_thread(poll_updates)
                await self.dispatch(notifications, removed)
            except Exception:
                logging.error("An exception occurred", exc_info=True)
            try:
                delay = await asyncio.to_thread(next_poll_delay, FAST_POLL_INTERVAL, POLL_INTERVAL)
            except Exception:
                logging.error("An exception occurred", exc_info=True)
                delay = POLL_INTERVAL
            await asyncio.sleep(delay)

    async def dispatch(self, notifications, removed):
        if not notifications and not removed:
            return
        with open(config.DATA_DIR / 'channel.json', 'r', encoding='utf8') as f:
            ch_data = json.load(f)
        messages = [(server_id, {"embed": build_update_embed(update)}) for server_id, update in notifications]
        messages += [(server_id, {"content": name+" 已不在動畫瘋新番列表，已自動取消訂閱"}) for server_id, name in removed]
        for server_id, kwargs in messages:
            channel = self.bot.get_channel(ch_data.get(str(server_id), 0))
            if channel is None:
                continue
            try:
                await channel.send(**kwargs)
            except discord.HTTPException:
                logging.error("An exception occurred", exc_info=True)


async def setup(bot):
    await bot.add_cog(Task(bot))
