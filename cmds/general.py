from discord.ext import commands
from discord import app_commands, Embed
from core.classes import Cog_Extension
from pathlib import Path
import discord
import json
import config

class 通用指令(Cog_Extension):
    def __init__(self, bot):
        self.bot = bot
        self.delete_menu = app_commands.ContextMenu(
            name='刪除訊息',
            callback=self.delete_message
        )
        self.bot.tree.add_command(self.delete_menu)

    @commands.command(name="ping")
    async def ping(self, ctx):
        """ping值測試"""
        await ctx.send(f'{round(self.bot.latency * 1000)}(ms)\n')

    @commands.command()
    async def leave(self, ctx):
        if ctx.author.id != config.OWNER_ID:
            return
        else:
            for guild in self.bot.guilds:
                if guild.id in config.GUILD_IDS:
                    continue
                else:
                    with open(config.DATA_DIR / 'message_count.json', "r") as f:
                        data = json.load(f)
                    if str(guild.id) not in data:
                        await guild.leave()
            await ctx.send("已離開所有伺服器")

    @commands.command(name="rolecolor")
    async def rolecolor(self, ctx, hex_: discord.Colour, role: discord.Role):
        """更改身分組顏色"""
        try:
            await role.edit(colour=hex_)
            await ctx.send(f"已將 {role.name} 的顏色更改為 {hex_}")
        except discord.Forbidden:
            await ctx.send("機器人權限不足（請確認機器人身分組在該身分組上方）。")
        except Exception as e:
            await ctx.send(f"發生錯誤: {e}")

    @commands.command()
    async def sername(self, ctx):
        if ctx.author.id != config.OWNER_ID:
            return
        else:
            name = "\n".join([guild.name for guild in self.bot.guilds])
            await ctx.send(name)

    @commands.command(name="test")
    async def test(self, ctx, arg):
        await ctx.send(f"測試回傳: {arg}")


    async def delete_message(self, interaction: discord.Interaction, message: discord.Message):
        # print(message.id)
        if message.author.id == self.bot.user.id:
            await message.delete()
            await interaction.response.send_message("已刪除", ephemeral=True)
        else:
            await interaction.response.send_message("只能刪除此機器人的訊息", ephemeral=True)


    @app_commands.command(name="help", description="提供指令的簡介")
    async def help(self, interaction: discord.Interaction):
        embeds = []
        await interaction.response.defer()
        for cog_name, cog in self.bot.cogs.items():
            if cog_name == "動畫瘋指令":
                embed = discord.Embed(
                    title=f"{cog_name}", description="動畫瘋自動通知的相關指令。", color=0x5568)
                embed.set_author(
                    name="巴哈姆特動畫瘋", icon_url="https://i.imgur.com/RF7sMkY.png")
            elif cog_name == "抽卡指令":
                embed = discord.Embed(
                    title=f"{cog_name}", description="模擬抽卡的相關指令，輸入-1200進行抽卡。", color=3447003)
                embed.set_author(
                    name="ブルーアーカイブ", icon_url="https://i.imgur.com/R1bu6V6.jpg")
            elif cog_name == "Embed開關指令":
                embed = discord.Embed(title=f"{cog_name}")
            else:
                continue

            for object in cog.__cog_app_commands__:
                # print(object.name)
                # print(object.description)
                embed.add_field(name=object.name,
                                value=object.description, inline=False)
                
            embeds.append(embed)

        if embeds:
            await interaction.followup.send(embeds=embeds)    


    @app_commands.command(name="歡迎訊息", description="設定歡迎訊息(會在設定該指令的地方發出)")
    @app_commands.describe(arg="內文")
    async def welcome_msg(self, interaction: discord.Interaction, arg: str):
        server_id = str(interaction.guild_id)
        channel_id = interaction.channel.id
        with open(config.DATA_DIR / 'welcome.json', 'r', encoding='utf8') as file:
            data = json.load(file)
        data[server_id] = [arg, channel_id]
        with open(config.DATA_DIR / 'welcome.json', 'w', encoding='utf8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        await interaction.response.send_message("已設定")



async def setup(bot):
    await bot.add_cog(通用指令(bot))