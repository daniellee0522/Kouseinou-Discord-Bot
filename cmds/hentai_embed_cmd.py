from discord.ext import commands
from discord import app_commands, Embed
from core.classes import Cog_Extension
from pathlib import Path
from functions.nhentai import test_embed, NumberView
from functions.wnacg import create_wnacg_embed, NumberView2
from functions.jm import jm_embed, NumberView3
from functions.supav import supjav_crawl
from bs4 import BeautifulSoup
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


    @app_commands.command(name="missav", description="回傳missav embed")
    @app_commands.describe(digit="番號")
    async def missav(self, interaction: discord.Interaction, digit: str):
        await interaction.response.defer()
        link=f"https://missav.ai/{digit}"
        try:
            response = await self.bot.missav_crawl.request(link)
            soup = BeautifulSoup(response, 'html.parser')
            description = soup.find('meta', attrs={'name': 'description'})
            title = soup.find('meta', attrs={'property': 'og:title'})
            image = soup.find('meta', attrs={'property': 'og:image'})
            embed = discord.Embed(title=title['content'], url=link)
            if image:
                embed.set_image(url=image['content'])
            if description:
                embed.description = description['content']
            embed.set_author(name="MissAV")
            await interaction.followup.send(embed=embed)
        except:
            await interaction.followup.send("找不到")


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
        view = NumberView(embed)
        await interaction.response.send_message(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(HentaiEmbedCmd(bot))