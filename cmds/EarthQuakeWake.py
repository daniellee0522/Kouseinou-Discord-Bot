import asyncio
import os
import discord
from core.classes import Cog_Extension
import json
from datetime import datetime
import config


INTENSITY = {"1": [0x808080, 1], "2": [0x0165cc, 2], "3": [0x01bb02, 3], "4": [0xebc000, 4], "5-": [
    0xff8400, 5], "5+": [0xe06300, 6], "6-": [0xff0000, 7], "6+": [0xb50000, 8], "7": [0x68009e, 9]}
ALERT_FILE = config.DATA_DIR / "test.json"
# 預警要快，維持每 0.2 秒檢查一次；但只看檔案修改時間，有變才讀檔
POLL_SECONDS = 0.2


def build_alert_embed(data):
    level = data['地震震度']
    if level not in INTENSITY:
        return discord.Embed(
            title=f'將要發生{level}級地震!!!',
            description=f"**預計{data['抵達秒數']}秒後抵達\n請注意安全。**。"
        )
    color, icon = INTENSITY[level]
    embed = discord.Embed(
        title=f"將要發生{level}級地震!!!",
        description=f"**預計{data['抵達秒數']}秒後抵達**。\n請注意安全。",
        color=color,
        timestamp=datetime.now()
    )
    embed.set_author(
        name="地震預警", icon_url="https://upload.wikimedia.org/wikipedia/commons/thumb/a/a9/ROC_Central_Weather_Bureau.svg/1200px-ROC_Central_Weather_Bureau.svg.png")
    embed.set_thumbnail(
        url=f"https://raw.githubusercontent.com/ExpTechTW/API/master/resource/int/{icon}.png")
    embed.set_image(
        url=f"https://exptech.com.tw/file/images/report/{icon}.png")
    return embed


class EarthQuakeWake(Cog_Extension):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._task = self.bot.loop.create_task(self.earth_quake_task())

    def cog_unload(self):
        self._task.cancel()

    async def earth_quake_task(self):
        await self.bot.wait_until_ready()
        last_stamp = None
        while not self.bot.is_closed():
            await asyncio.sleep(POLL_SECONDS)
            try:
                st = os.stat(ALERT_FILE)
            except FileNotFoundError:
                continue
            stamp = (st.st_mtime_ns, st.st_size)
            if stamp == last_stamp:
                continue
            last_stamp = stamp
            # 讀檔或送出出錯不能讓整個迴圈停掉，否則之後的預警都不會發
            try:
                await self.check_alert()
            except Exception as e:
                print(f"[earthquake] 處理預警失敗: {e!r}", flush=True)

    async def check_alert(self):
        with open(ALERT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("flag") != "1":
            return
        # 先把 flag 清掉再發送，發送途中出錯也不會一直重發同一筆
        data["flag"] = "0"
        with open(ALERT_FILE, 'w', encoding='utf8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

        embed = build_alert_embed(data)
        with open(config.DATA_DIR / "alert.json", "r") as f:
            channel_ids = json.load(f)
        for channel_id in channel_ids:
            channel = self.bot.get_channel(channel_id)
            if channel is None:
                continue
            try:
                await channel.send(embed=embed)
            except discord.HTTPException as e:
                print(f"[earthquake] 無法發送到 {channel_id}: {e!r}", flush=True)


async def setup(bot):
    await bot.add_cog(EarthQuakeWake(bot))
