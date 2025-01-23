import discord
from discord import app_commands
from discord.ext import commands
from discord.ext.commands import has_permissions
import json
import datetime
import pytz
from functions.slot import lock_channel,unlock_channel
from core.classes import Cog_Extension

class 抽卡指令(Cog_Extension):
    @app_commands.command(name="統計", description="統計抽卡數據")
    async def 統計(self,interaction:discord.Interaction):
        """
        統計抽卡數據
        """
        user_id = str(interaction.user.id)
        user = interaction.user
        name = str(user.global_name)
        with open('json/gacha.json', 'r', encoding = 'utf8') as file:
            data = json.load(file)
        try:
            user = data[user_id].copy()
            SSR_percentage = '{:.2%}'.format(user["SSR"]/user["total"])
            SR_percentage='{:.2%}'.format(user["SR"]/user["total"])
            R_percentage='{:.2%}'.format(user["R"]/user["total"])
            PU_percentage='{:.2%}'.format(user["PU"]/user["total"])
            embed = discord.Embed(
                                                                title = f'{name}的抽卡統計', 
                                                                description="PU : {} 抽 ({})\n:star::star::star: (含PU) : {} 抽 ({})\n:star::star: : {} 抽 ({})\n:star: : {}抽  ({})\n總抽數 : {} 抽 ({}井)".format(
                user["PU"],PU_percentage,user["SSR"],SSR_percentage,user["SR"],SR_percentage,user["R"],R_percentage,user["total"],user["total"]//200
                )
                                                                ,
                                                                color = 3447003,
                                                                timestamp = datetime.datetime.now(pytz.utc)
                                                                )
            embed.set_author(name="ブルーアーカイブ", icon_url="https://i.imgur.com/R1bu6V6.jpg")
            await interaction.response.send_message(embed=embed)
        except:
            await interaction.response.send_message("未有抽卡紀錄")
        pass

    @app_commands.command(name="歸零", description="歸零抽卡數據")
    async def 歸零(self,interaction:discord.Interaction):
        """
        歸零抽卡數據
        """

        user_id = str(interaction.user.id)
        with open('json/gacha.json', 'r', encoding = 'utf8') as file:
            data = json.load(file)
        try:
            data.pop(user_id)
            with open('json/gacha.json','w',encoding='utf8') as f:
                json.dump(data,f,ensure_ascii=False,indent = 4)
            await interaction.response.send_message("已歸零")
        except:
            await interaction.response.send_message("未有抽卡紀錄")
    
    @app_commands.command(name="上鎖", description="上鎖後不能在該頻道抽卡(此指令限管理員使用)")
    @has_permissions(administrator=True)
    async def 上鎖(self,interaction:discord.Interaction):
        """
        上鎖後不能在該頻道抽卡(此指令限管理員使用)
        """
        channel_id= interaction.channel.id
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("你沒有執行此指令的權限")
            return
        else:
            response = lock_channel(channel_id)
            if response == "locked":
                await interaction.response.send_message("已上鎖")
                return
            elif response == "already locked":
                await interaction.response.send_message("這個頻道已經上鎖過了。")
                return
            
    @app_commands.command(name="解鎖", description="解鎖上鎖的頻道(此指令限管理員使用)")
    @has_permissions(administrator=True)
    async def 解鎖(self,interaction:discord.Interaction):
        """
        解鎖上鎖的頻道(此指令限管理員使用)
        """
        channel_id= interaction.channel.id
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("你沒有執行此指令的權限")
            return
        else:
            response = unlock_channel(channel_id)
            if response == "not locked":
                await interaction.response.send_message("這個頻道並未上鎖。")
                return
            elif response == "unlocked":
                await interaction.response.send_message("已解鎖")
    
    @app_commands.command(name="換池", description="更換PU角色")
    async def 換池(self,interaction:discord.Interaction):
        with open('json/pu.json','r',encoding='utf8') as f:
            data = json.load(f)
            keylist = list(data.keys())
            print(keylist)
            for i in range(len(keylist)):
                if data[keylist[i]] == True:
                    data[keylist[i]] = False
                    try:
                        data[keylist[i+1]] = True
                    except:
                        data[keylist[0]] = True
                    break
        with open('json/pu.json','w',encoding='utf8') as f:
            json.dump(data,f,ensure_ascii=False,indent = 4)
        await interaction.response.send_message("已換池")
async def setup(bot):
    await bot.add_cog(抽卡指令(bot))