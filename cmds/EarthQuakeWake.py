import urllib.request as req
from urllib.parse import quote
import asyncio
import discord
from core.classes import Cog_Extension
import json
from datetime import datetime


class EarthQuakeWake(Cog_Extension):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        async def earth_quake_task2():
            dict_ = {"1": [0x808080, 1], "2": [0x0165cc, 2], "3": [0x01bb02, 3], "4": [0xebc000, 4], "5-": [
                0xff8400, 5], "5+": [0xe06300, 6], "6-": [0xff0000, 7], "6+": [0xb50000, 8], "7": [0x68009e, 9]}
            await self.bot.wait_until_ready()
            while not self.bot.is_closed():
                # 爬取資訊
                with open("json/earthquake.json", "r", encoding="utf-8") as f:
                    data = json.load(f)

                if data["flag"] == "1":
                    # 建立 embed
                    try:
                        embed = discord.Embed(
                            title=f"將要發生{data['地震震度']}級地震!!!",
                            description=f"**預計{data['抵達秒數']}秒後抵達**。\n請注意安全。",
                            color=dict_[data['地震震度']][0],
                            timestamp=datetime.now()
                        )
                        embed.set_author(
                            name="地震預警", icon_url="https://upload.wikimedia.org/wikipedia/commons/thumb/a/a9/ROC_Central_Weather_Bureau.svg/1200px-ROC_Central_Weather_Bureau.svg.png")
                        embed.set_thumbnail(
                            url=f"https://raw.githubusercontent.com/ExpTechTW/API/master/resource/int/{dict_[data['地震震度']][1]}.png")
                        embed.set_image(
                            url=f"https://exptech.com.tw/file/images/report/{dict_[data['地震震度']][1]}.png")
                    except:
                        embed = discord.Embed(
                            title=f'將要發生{data["地震震度"]}級地震!!!',
                            description=f"**預計{data['抵達秒數']}秒後抵達\n請注意安全。**。"
                        )
                    # 發送至各頻道
                    with open("json/alert.json", "r") as f:
                        channel = json.load(f)
                    for channel_id in channel:
                        self.channel = self.bot.get_channel(channel_id)
                        await self.channel.send(embed=embed)
                    data["flag"] = "0"
                    with open('json/earthquake.json', 'w', encoding='utf8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=4)
                await asyncio.sleep(0.2)
        self.bot.loop.create_task(earth_quake_task2())


async def setup(bot):
    await bot.add_cog(EarthQuakeWake(bot))
