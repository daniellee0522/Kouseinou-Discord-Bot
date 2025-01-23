import json
import datetime
import pytz
import discord
from discord.ext import commands
from discord.ui import Button, View
from discord import app_commands
from functions.ani_gamer import anime_get_info, anime_lst, anime_get_info_add
from core.classes import Cog_Extension


class 動畫瘋指令(Cog_Extension):
    @app_commands.command(name="查詢新番", description="查詢新動畫資訊並訂閱其通知")
    @app_commands.describe(anime_name="輸入動畫名(可接受略寫)", r="若有年齡限制輸入R，沒有則無需輸入")
    async def 查詢新番(self, interaction: discord.Interaction, anime_name: str, r: str = "y"):
        R_18 = r.upper()
        """
        查詢新番資訊並訂閱其通知
        使用方法:$查詢新番 {番名} {是否是R-18(若有則輸入R，沒有則無需輸入)}
        """
        try:
            server_id = interaction.guild_id
            if server_id == None:
                await interaction.response.send_message("Not available")
                return
            await interaction.response.defer()
            inf = anime_get_info(anime_name, R_18)
            if inf != [] and inf != "fail to connect":
                with open('json/sub.json', 'r', encoding='utf8') as f:
                    data = json.load(f)
                lst = []
                try:
                    for i in range(len(data[str(server_id)])):
                        lst.append(data[str(server_id)][i]["name"])
                except KeyError:
                    data[str(server_id)] = []
                    for i in range(len(data[str(server_id)])):
                        lst.append(data[str(server_id)][i]["name"])
                if inf[0] in lst:
                    button = Button(label="已訂閱")
                    button.disabled = True
                else:
                    button = Button(label="訂閱")

                    async def button_callback(i):
                        button1 = Button(label="已訂閱", disabled=True)
                        view1 = View()
                        view1.add_item(button1)
                        await i.response.edit_message(view=view1)
                        anime_get_info_add(inf[0], server_id, R_18)
                    button.callback = button_callback
                view = View()
                view.add_item(button)
                embed = discord.Embed(
                    title=inf[0],
                    description="目前更新至"+inf[1]+'\n'+inf[2],
                    color=0x5568,
                    timestamp=datetime.datetime.now(pytz.utc)
                )
                embed.set_author(
                    name="巴哈姆特動畫瘋", icon_url="https://i.imgur.com/RF7sMkY.png")
                embed.set_thumbnail(url=inf[3])
                # embed.set_thumbnail(url = 'https://i.imgur.com/0j3pxid.jpg')
                await interaction.followup.send(embed=embed, view=view)
            elif inf == "fail to connect":
                await interaction.followup.send("連線錯誤")
            else:
                embed = discord.Embed(description="此動畫不存在或並非更新中", color=0x5568)
                await interaction.followup.send(embed=embed)
        except AttributeError:
            pass

    @app_commands.command(name="新番列表", description="執行指令後回傳當季新動畫列表")
    async def 新番列表(self, interaction: discord.Interaction):
        """
        執行指令後回傳當季新番列表
        """
        try:
            server_id = interaction.guild_id
            await interaction.response.defer()
            inf = anime_lst()
            if inf == "fail to connect":
                await interaction.response.send_message("連線錯誤")
            else:
                if len(inf) <= 25:
                    embed = discord.Embed(
                        title="新番列表",
                        description="目前正在更新的動畫",
                        color=0x5568, timestamp=datetime.datetime.now(pytz.utc)
                    )
                    embed.set_author(
                        name="巴哈姆特動畫瘋", icon_url="https://i.imgur.com/RF7sMkY.png")
                    for i in range(len(inf)):
                        embed.add_field(
                            name=inf[i][0],
                            value="更新至"+inf[i][1] +
                            '\n'+inf[i][3]+inf[i][4] +
                            "更新\n"+inf[i][2], inline=True
                        )
                    await interaction.followup.send(embed=embed)
                else:
                    step = 24
                    formed_inf = [inf[i:i+step]
                                  for i in range(0, len(inf), step)]
                    # print(len(inf))
                    # print(len(formed_inf))
                    # print(len(formed_inf[0]),len(formed_inf[1]))
                    for i in range(len(formed_inf)):
                        if i == 0:
                            embed = discord.Embed(
                                title="新番列表",
                                description="目前正在更新的動畫",
                                color=0x5568,
                                timestamp=datetime.datetime.now(pytz.utc)
                            )
                            embed.set_author(
                                name="巴哈姆特動畫瘋", icon_url="https://i.imgur.com/RF7sMkY.png")
                        else:
                            embed = discord.Embed(
                                color=0x5568, timestamp=datetime.datetime.now(pytz.utc))
                        for j in range(len(formed_inf[i])):
                            embed.add_field(
                                name=formed_inf[i][j][0],
                                value="更新至"+formed_inf[i][j][1]+'\n' +
                                formed_inf[i][j][3]+formed_inf[i][j][4] +
                                "更新\n" +
                                formed_inf[i][j][2],
                                inline=True
                            )
                        if i == 0:
                            await interaction.followup.send(embed=embed)
                        else:
                            await interaction.followup.send(embed=embed)
        except AttributeError:
            pass

    @app_commands.command(name="訂閱", description="訂閱指定動畫")
    @app_commands.describe(anime_name="輸入動畫名(可接受略寫)", r="若有年齡限制輸入R，沒有則無需輸入")
    async def 訂閱(self, interaction: discord.Interaction, anime_name: str, r: str = "n"):
        R_18 = r.upper()
        """
        使用方法:$訂閱 {番名} {是否是R-18(若有則輸入R，沒有則無需輸入)}
        """
        if R_18 == "y":
            R_18 = "n"
        try:
            server_id = interaction.guild_id
            if server_id == None:
                await interaction.response.send_message("Not available")
                return
            await interaction.response.defer()
            result = anime_get_info_add(anime_name, server_id, R_18)
            if result == "repeated":
                print("test")
                await interaction.followup.send("已經訂閱過了")
            elif result == "not found":
                await interaction.followup.send("此動畫不存在或並非更新中")
            else:
                await interaction.followup.send("已訂閱 "+result)
        except AttributeError:
            pass

    @app_commands.command(name="刪除訂閱", description="刪除訂閱動畫")
    @app_commands.describe(anime_name="輸入動畫名(可接受略寫)", r="若有年齡限制輸入R，沒有則無需輸入")
    async def 刪除訂閱(self, interaction: discord.Interaction, anime_name: str, r: str = "n"):
        R_18 = r.upper()
        """
        使用方法:$刪除訂閱 {番名} {是否是R-18(若有則輸入R，沒有則無需輸入)}
        """
        dict_ = {}
        try:
            server_id = interaction.guild_id
            if server_id == None:
                await interaction.response.send_message("Not available")
                return
            with open('json/sub.json', 'r', encoding='utf8') as f:
                data = json.load(f)
            try:
                for i in range(len(data[str(server_id)])):
                    if anime_name in data[str(server_id)][i]["name"]:
                        dict_[i] = data[str(server_id)][i]["name"]
                print(dict_)
                if len(dict_) > 1:
                    # print("不只一個")
                    if R_18 == "r" or R_18 == "R":
                        for key, value in dict_.items():
                            if "(年齡限制)" in value:
                                await interaction.response.send_message("已刪除"+value)
                                data[str(server_id)].pop(key)
                                with open('json/sub.json', 'w', encoding='utf8') as f:
                                    json.dump(
                                        data, f, ensure_ascii=False, indent=4)
                                return
                    else:
                        for key, value in dict_.items():
                            if "(年齡限制)" not in value:
                                await ("已刪除"+value)
                                data[str(server_id)].pop(key)
                                with open('json/sub.json', 'w', encoding='utf8') as f:
                                    json.dump(
                                        data, f, ensure_ascii=False, indent=4)
                                return
                elif len(dict_) == 1:
                    print("一個")
                    if R_18 == "r" or R_18 == "R":
                        print("有R")
                        for key, value in dict_.items():
                            if "(年齡限制)" not in value:
                                await interaction.response.send_message("沒有訂閱此動畫的年齡限制版")
                                return
                            else:
                                await interaction.response.send_message("已刪除"+data[str(server_id)][key]["name"])
                                data[str(server_id)].pop(key)
                                with open('json/sub.json', 'w', encoding='utf8') as f:
                                    json.dump(
                                        data, f, ensure_ascii=False, indent=4)
                                return
                    else:
                        for key, value in dict_.items():
                            await interaction.response.send_message("已刪除"+data[str(server_id)][key]["name"])
                            data[str(server_id)].pop(key)
                            with open('json/sub.json', 'w', encoding='utf8') as f:
                                json.dump(
                                    data, f, ensure_ascii=False, indent=4)
                            return

                else:
                    await interaction.response.send_message("沒有訂閱此動畫")
                    return
            except KeyError:
                await interaction.response.send_message("沒有訂閱此動畫")
        except AttributeError:
            pass

    @app_commands.command(name="訂閱列表", description="查看已訂閱的番")
    async def 訂閱列表(self,  interaction: discord.Interaction):
        """
        查看已訂閱的番
        """
        week_lst = {1: "星期一", 2: "星期二", 3: "星期三",
                    4: "星期四", 5: "星期五", 6: "星期六", 7: "星期日"}
        try:
            server_id = interaction.guild_id
            if server_id == None:
                await interaction.response.send_message("Not available")
                return
            embed = discord.Embed(
                title="訂閱列表",
                description="目前已訂閱動畫",
                color=0x5568,
                timestamp=datetime.datetime.now(pytz.utc)
            )
            embed.set_author(
                name="巴哈姆特動畫瘋", icon_url="https://i.imgur.com/RF7sMkY.png")
            with open('json/sub.json', 'r', encoding='utf8') as f:
                data = json.load(f)
            try:
                if data[str(server_id)] == []:
                    await interaction.response.send_message(content="未訂閱任何動畫")
                    return

                data[str(server_id)].sort(key=lambda x: (
                    x["update_date"], x["update_time"], x["name"]))
                with open('json/sub.json', 'w', encoding='utf8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)

                for anime in data[str(server_id)]:
                    a = anime["name"]
                    time_lst = list(anime["update_time"])
                    time_lst.insert(2, ":")
                    time = ''.join(time_lst)
                    embed.add_field(name=a,
                                    value=week_lst[anime["update_date"]
                                                   ]+time+" 更新",
                                    inline=True
                                    )
                await interaction.response.send_message(embed=embed)
            except:
                await interaction.response.send_message(content="未訂閱任何動畫")
        except AttributeError:
            pass

    @app_commands.command(name="設定頻道", description="將更新通知設定在發出指令的頻道中")
    async def 設定頻道(self, interaction: discord.Interaction):
        """
        將更新通知設定在發出指令的頻道中
        """
        try:
            server_id = interaction.guild_id
            if server_id == None:
                await interaction.response.send_message("Not available")
                return
            channel_id = interaction.channel_id
            with open('json/channel.json', 'r', encoding='utf8') as f:
                j_data = json.load(f)
            try:
                if j_data[str(server_id)] == channel_id:
                    await interaction.response.send_message(content="這個頻道已經設定過了")
                else:
                    j_data[str(server_id)] = channel_id
                    with open('json/channel.json', 'w', encoding='utf8') as f:
                        json.dump(j_data, f, ensure_ascii=False, indent=4)
                    await interaction.response.send_message(content="已將通知設定在此頻道")
            except:
                j_data[str(server_id)] = channel_id
                with open('json/channel.json', 'w', encoding='utf8') as f:
                    json.dump(j_data, f, ensure_ascii=False, indent=4)
                await interaction.response.send_message(content="已將通知設定在此頻道")
        except AttributeError:
            pass


async def setup(bot):
    await bot.add_cog(動畫瘋指令(bot))
