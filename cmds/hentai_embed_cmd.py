from discord.ext import commands
from discord import app_commands, Embed
from core.classes import Cog_Extension
from pathlib import Path
from functions.nhentai import test_embed, NumberView
from functions.wnacg import create_wnacg_embed, NumberView2
from functions.jm import jm_embed, NumberView3
from functions.supav import supjav_crawl, supjav_search_embed
from functions.missav_func import fetch_missav_embed, missav_fallback_embed
from functions.jable import jable_embed
import asyncio
import discord
import json
import config

class HentaiEmbedCmd(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="cookies", description="更新cookies(你沒權限)")
    @app_commands.describe(cf_clearance="cookie1", csrftoken="cookie2")
    async def cookies(self, interaction: discord.Interaction, cf_clearance: str, csrftoken: str):
        if interaction.user.id != config.OWNER_ID:
            await interaction.response.send_message("你沒有權限使用此指令")
        else:
            dict_ = {"cf_clearance": cf_clearance, "csrftoken": csrftoken}
            with open(config.DATA_DIR / 'cookies.json', 'w', encoding='utf8') as f:
                json.dump(dict_, f, ensure_ascii=False, indent=4)


    @app_commands.command(name="wnacg", description="回傳wnacg embed")
    @app_commands.describe(digit="神秘數字")
    async def wnacg(self, interaction: discord.Interaction, digit: int):
        digit = str(digit)
        await interaction.response.defer()
        embed = await create_wnacg_embed(session=self.bot.session, digit=digit)
        if embed == 404:
            await interaction.followup.send("不存在")
            return
        elif embed == 403:
            await interaction.followup.send("存取遭拒")
            return
        view = NumberView2(session=self.bot.session, embed=embed)
        await interaction.followup.send(embed=embed, view=view)


    @app_commands.command(name="av番號查詢", description="查詢av番號，優先順序: missav > jable > supjav")
    @app_commands.describe(digit="番號")
    async def missav(self, interaction: discord.Interaction, digit: str):
        await interaction.response.defer()

        # 三個來源一開始就同時起飛，不用等 missav 爬完才決定要不要查 jable/supjav；
        # 但 missav 有結果的話就不用再等 jable/supjav（它們通常比 missav 慢很多），
        # 不然明明 missav 秒回也會被拖著一起等，等於變得更慢。
        # 優先權 missav > jable > supjav (後兩者由 missav_fallback_embed 內部處理)
        missav_task = asyncio.create_task(fetch_missav_embed(self.bot.missav_crawl, digit))
        fallback_task = asyncio.create_task(missav_fallback_embed(self.bot.jable_crawl, digit))

        try:
            embed = await missav_task
            missav_failed = False
        except Exception:
            embed = None
            missav_failed = True

        if embed is None:
            try:
                embed = await fallback_task
            except Exception:
                embed = None
        else:
            # missav 已經有答案，jable/supjav 的結果用不到了，讓它在背景跑完就好，
            # 不要因為沒人 await 例外而跳警告
            fallback_task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)

        if embed:
            await interaction.followup.send(embed=embed)
        elif missav_failed:
            await interaction.followup.send("目前無法取得資料，請稍後再試。")
        else:
            await interaction.followup.send("找不到這個番號（MissAV、Jable、Supjav 都沒有）")

    @app_commands.command(name="missav", description="回傳missav embed")
    @app_commands.describe(digit="番號")
    async def missav_only(self, interaction: discord.Interaction, digit: str):
        await interaction.response.defer()
        try:
            embed = await fetch_missav_embed(self.bot.missav_crawl, digit)
        except Exception:
            embed = None
        if embed is None:
            await interaction.followup.send("找不到相關影片或存取遭拒")
            return
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="jable", description="回傳jable embed")
    @app_commands.describe(digit="番號")
    async def jable(self, interaction: discord.Interaction, digit: str):
        await interaction.response.defer()
        embed = await jable_embed(self.bot.jable_crawl, digit)
        if embed is None:
            await interaction.followup.send("找不到相關影片或存取遭拒")
            return
        await interaction.followup.send(embed=embed)


    @app_commands.command(name="supjav", description="回傳supjav embed")
    @app_commands.describe(digit="番號")
    async def supjav(self, interaction: discord.Interaction, digit: str):
        await interaction.response.defer()
        try:
            embed = await supjav_search_embed(digit)
        except Exception:
            embed = None
        if embed is None:
            await interaction.followup.send("找不到相關影片或存取遭拒")
            return
        await interaction.followup.send(embed=embed)


    @app_commands.command(name="jm", description="回傳禁漫天堂 embed")
    @app_commands.describe(digit="神秘數字")
    async def jm(self, interaction: discord.Interaction, digit: int):
        url = f"https://18comic.vip/album/{digit}/"
        try:
            await interaction.response.defer()
            embed = jm_embed(url)
            view = NumberView3(embed=embed)
            await interaction.followup.send(embed=embed, view=view)
        except:
            await interaction.followup.send("不存在或存取遭拒")
            

    @app_commands.command(name="nhentai", description="回傳nhentai embed")
    @app_commands.describe(digit="神秘數字")
    async def nh(self, interaction: discord.Interaction, digit: int):
        digit = str(digit)
        with open(config.DATA_DIR / 'cookies.json', 'r', encoding='utf8') as file:
            data = json.load(file)
        cf_clearance = data["cf_clearance"]
        csrftoken = data["csrftoken"]
        embed = await test_embed(session=self.bot.session, sec5h= self.bot.missav_crawl,
            digit=digit, cf_clearance=cf_clearance, csrftoken=csrftoken)
        if embed == 404:
            await interaction.response.send_message("不存在")
            return
        elif embed == 403:
            await interaction.response.send_message("存取遭拒")
            return
        view = NumberView(embed=embed, session=self.bot.session, sec5h=self.bot.missav_crawl)
        await interaction.response.send_message(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(HentaiEmbedCmd(bot))