import json
import asyncio
import datetime
import pytz
import discord
from functions.ani_gamer import check_and_update
from core.classes import Cog_Extension

class Task(Cog_Extension):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        async def time_tesk():
            await self.bot.wait_until_ready()
            while not self.bot.is_closed():
                with open('json/channel.json','r',encoding='utf8') as f:
                    ch_data = json.load(f)
                for server_id,channel_id in ch_data.items():
                    now_time=datetime.datetime.now().strftime("%H%M")
                    now_weekday=datetime.datetime.now().weekday()
                    now_sec=int(datetime.datetime.now().strftime("%S"))
                    with open('json/sub.json','r',encoding='utf8') as f:
                        j_data = json.load(f)
                    if j_data == {}:
                        await asyncio.sleep(1)
                        continue
                    try:
                        for i in range(len(j_data[str(server_id)])):
                            if now_time == j_data[str(server_id)][i]["update_time"] and now_weekday+1 ==  j_data[str(server_id)][i]["update_date"] and now_sec>1:
                                try:
                                    response = check_and_update(i,server_id)
                                    if response == "already updated":
                                        pass
                                    elif response == "fail to connect":
                                        pass
                                    elif response[0] == "n":
                                        pass
                                    else:
                                        embed=discord.Embed(
                                                        title = j_data[str(server_id)][i]["name"]+"更新到"+response[0]+"了!", 
                                                        description="觀看網址:\n"+response[1],
                                                        color = 0x5568,timestamp = datetime.datetime.now(pytz.utc)
                                                        )
                                        embed.set_author(name="巴哈姆特動畫瘋", icon_url="https://i.imgur.com/RF7sMkY.png")
                                        embed.set_image(url = response[2])
                                        self.channel=self.bot.get_channel(channel_id)
                                        await self.channel.send(embed=embed)
                                except Exception as error:
                                    print("An exception occurred:", type(error).__name__)
                                    continue
                    except Exception as error:
                        pass
                await asyncio.sleep(1)
        self.bot.loop.create_task(time_tesk())

async def setup(bot):
    await bot.add_cog(Task(bot))