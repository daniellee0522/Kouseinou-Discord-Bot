import discord
from discord import app_commands
from discord.ext import commands, tasks
import json
import datetime
import pytz
from functions.slot import lock_channel,unlock_channel
from core.classes import Cog_Extension
from functions.ba_banner import ensure_gacha_emojis, sync_pu, pu_names, warm_student_names, PU_FILE
from functions.app_emoji import app_emojis, EMOJI_TAG
from functions.gacha_play import GachaAgainView
from functions.gacha import new_system_active
import config

class 抽卡指令(Cog_Extension):
    async def cog_load(self):
        # 「再抽十連」按鈕：重開機後舊的抽卡訊息也能按
        self.bot.add_view(GachaAgainView())

    @commands.Cog.listener()
    async def on_ready(self):
        await ensure_gacha_emojis(self.bot)
        await warm_student_names(self.bot.session)
        if not self.sync_banner.is_running():
            self.sync_banner.start()

    async def cog_unload(self):
        self.sync_banner.cancel()

    @tasks.loop(hours=1)
    async def sync_banner(self):
        """每小時對一次國際服目前的 PU 卡池（SchaleDB），換期了就更新 pu.json"""
        try:
            await sync_pu(self.bot)
        except Exception as e:
            print(f"[ba] 同步 PU 卡池失敗: {e!r}", flush=True)

    @app_commands.command(name="統計", description="統計抽卡數據")
    async def 統計(self,interaction:discord.Interaction):
        """
        統計抽卡數據
        """
        user_id = str(interaction.user.id)
        user = interaction.user
        name = str(user.global_name)
        with open(config.DATA_DIR / 'gacha.json', 'r', encoding = 'utf8') as file:
            data = json.load(file)
        try:
            user = data[user_id].copy()
            SSR_percentage = '{:.2%}'.format(user["SSR"]/user["total"])
            SR_percentage='{:.2%}'.format(user["SR"]/user["total"])
            R_percentage='{:.2%}'.format(user["R"]/user["total"])
            PU_percentage='{:.2%}'.format(user["PU"]/user["total"])
            embed = discord.Embed(
                                                                title = f'{name}的抽卡統計', 
                                                                description="PU : {} 抽 ({})\n:star::star::star: (含PU) : {} 抽 ({})\n:star::star: : {} 抽 ({})\n:star: : {}抽  ({})\n總抽數 : {} 抽{}".format(
                user["PU"],PU_percentage,user["SSR"],SSR_percentage,user["SR"],SR_percentage,user["R"],R_percentage,user["total"],
                f"\n招募充能 : {user.get('charge', 0)}/200（第 100 抽必定 ★3，第 200 抽必定 PU）" if new_system_active()
                else f" ({user['total'] // 200}井)"
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
        with open(config.DATA_DIR / 'gacha.json', 'r', encoding = 'utf8') as file:
            data = json.load(file)
        try:
            data.pop(user_id)
            with open(config.DATA_DIR / 'gacha.json','w',encoding='utf8') as f:
                json.dump(data,f,ensure_ascii=False,indent = 4)
            await interaction.response.send_message("已歸零")
        except:
            await interaction.response.send_message("未有抽卡紀錄")
    
    @app_commands.command(name="上鎖", description="上鎖後不能在該頻道抽卡(此指令限管理員使用)")
    @app_commands.guild_only()
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
    @app_commands.guild_only()
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
    
    @app_commands.command(name="換池", description="選擇目前的 PU 角色")
    async def 換池(self, interaction: discord.Interaction):
        try:
            with open(PU_FILE, 'r', encoding='utf8') as f:
                pool = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pool = {}
        if not pool:
            return await interaction.response.send_message("目前沒有 PU 卡池（每小時會自動同步國際服的卡池）。", ephemeral=True)
        await interaction.response.defer()
        names = await pu_names(self.bot.session, list(pool))
        view = PoolSelectView(self.bot, interaction.user.id, pool, names)
        await interaction.followup.send(view.summary(), view=view)


class PoolSelectView(discord.ui.View):
    """/換池 的選單：列出卡池裡的角色（頭像表情＋名字），執行指令的人選一個當 PU"""

    def __init__(self, bot, owner_id, pool, names):
        super().__init__(timeout=180)
        self.bot, self.owner_id, self.pool, self.names = bot, owner_id, pool, names
        fix = app_emojis(bot).fix
        self.fix = fix
        options = []
        for key, current in list(pool.items())[:25]:
            emoji = fix(key)
            options.append(discord.SelectOption(label=names[key][:100], value=key, default=current,
                                                emoji=emoji if EMOJI_TAG.fullmatch(emoji) else None))
        self.select = discord.ui.Select(placeholder="選擇 PU 角色", options=options)
        self.select.callback = self.on_select
        self.add_item(self.select)

    def summary(self):
        current = next((k for k, v in self.pool.items() if v), None)
        return f"目前 PU：{self.fix(current)} **{self.names[current]}**" if current else "目前沒有選定的 PU。"

    async def on_select(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            return await interaction.response.send_message("只有執行 /換池 的人可以選。", ephemeral=True)
        chosen = self.select.values[0]
        async with self.bot.data_lock:
            with open(PU_FILE, 'r', encoding='utf8') as f:
                pool = json.load(f)
            if chosen not in pool:
                return await interaction.response.edit_message(content="卡池已經換期了，請重新執行 /換池。", view=None)
            pool = {key: key == chosen for key in pool}
            with open(PU_FILE, 'w', encoding='utf8') as f:
                json.dump(pool, f, ensure_ascii=False, indent=4)
        self.pool = pool
        self.stop()
        await interaction.response.edit_message(content=f"已換池，{self.summary()}", view=None)


async def setup(bot):
    await bot.add_cog(抽卡指令(bot))