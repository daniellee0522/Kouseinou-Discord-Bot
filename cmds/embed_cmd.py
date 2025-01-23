import discord
from discord.ext import commands
from discord.ui import Button, View
from discord import app_commands
from functions.embed_permission import *
from core.classes import Cog_Extension
from discord.app_commands import Choice


class Embed開關指令(Cog_Extension):
    @app_commands.command(name="解析網頁開關", description="開關伺服器是否解析網址")
    @app_commands.describe(website="選擇網站")
    @app_commands.choices(
        website=[
            Choice(name="巴哈場外", value="baha"),
            Choice(name="nhentai", value="nh"),
            Choice(name="wnacg", value="wn"),
            Choice(name="禁漫天堂", value="jm")
        ]
    )
    async def 場外開關(self, interaction: discord.Interaction, website: Choice[str]):
        arg = website.value
        server_id = interaction.guild_id
        if server_id == None:
            interaction.response.send_message("Not available")
            return
        text = change_permission(server_id=server_id, arg=arg)
        await interaction.response.send_message(content=text)


async def setup(bot):
    await bot.add_cog(Embed開關指令(bot))
