from discord.ext import commands
from discord import app_commands, Embed
from core.classes import Cog_Extension
from pathlib import Path
import discord
import json
import config

# /help 顯示的分類，key 為 Cog 名稱；沒列在這裡的 Cog 不會出現在 help
HELP_SECTIONS = {
    "通用指令": {
        "title": "通用指令",
        "description": "一般功能。",
        "color": 0x95A5A6,
        "extra": [
            ("$ping", "查看機器人延遲"),
            ("$rolecolor <色碼> <@身分組>", "更改身分組顏色，例如 `$rolecolor #ff0000 @成員`"),
        ],
    },
    "動畫瘋指令": {
        "title": "動畫瘋指令",
        "description": "動畫瘋自動通知的相關指令。",
        "color": 0x00B4D8,
        "author": {"name": "巴哈姆特動畫瘋", "icon_url": "https://i.imgur.com/RF7sMkY.png"},
    },
    "抽卡指令": {
        "title": "抽卡指令",
        "description": "模擬抽卡的相關指令，在聊天輸入 `-1200` 進行抽卡。",
        "color": 0x3498DB,
        "author": {"name": "ブルーアーカイブ", "icon_url": "https://i.imgur.com/R1bu6V6.jpg"},
    },
    "Embed開關指令": {
        "title": "網址解析開關",
        "description": "開關本伺服器是否自動解析特定網站的網址（需要管理伺服器權限）。",
        "color": 0xE67E22,
    },
    "HentaiEmbedCmd": {
        "title": "NSFW 查詢指令",
        "description": "僅在 NSFW 頻道顯示。",
        "color": 0xE91E63,
        "nsfw": True,
    },
}
# 不在 help 中顯示的指令（擁有者專用或 help 本身）
HIDDEN_COMMANDS = {"cookies", "excookies", "help"}

class 通用指令(Cog_Extension):
    def __init__(self, bot):
        self.bot = bot
        self._mentions = None
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
            try:
                with open(config.DATA_DIR / 'message_count.json', "r") as f:
                    data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                await ctx.send(f"讀取 message_count.json 失敗，已取消：{e}")
                return
            # 檔案被清空時會把所有伺服器都判定為不活躍，直接中止
            if not data:
                await ctx.send("message_count.json 是空的，已取消")
                return
            targets = [g for g in self.bot.guilds
                       if g.id not in config.GUILD_IDS and str(g.id) not in data]
            for guild in targets:
                await guild.leave()
            await ctx.send(f"已離開 {len(targets)} 個不活躍的伺服器")

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


    async def _command_mentions(self) -> dict:
        """取得 {指令名: </指令名:id>}，讓 help 裡的指令可以直接點擊；只抓一次並快取"""
        if self._mentions is None:
            try:
                fetched = await self.bot.tree.fetch_commands()
                self._mentions = {c.name: c.mention for c in fetched}
            except discord.HTTPException:
                return {}
        return self._mentions

    @app_commands.command(name="help", description="提供指令的簡介")
    async def help(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        mentions = await self._command_mentions()
        is_nsfw = isinstance(interaction.channel, (discord.TextChannel, discord.Thread)) and interaction.channel.is_nsfw()

        embeds = []
        for cog_name, section in HELP_SECTIONS.items():
            cog = self.bot.cogs.get(cog_name)
            if cog is None or (section.get("nsfw") and not is_nsfw):
                continue
            embed = discord.Embed(title=section["title"], description=section["description"], color=section["color"])
            if "author" in section:
                embed.set_author(**section["author"])

            for cmd in cog.walk_app_commands():
                if cmd.name in HIDDEN_COMMANDS or len(embed.fields) >= 25:
                    continue
                params = " ".join(f"<{p.display_name}>" if p.required else f"[{p.display_name}]" for p in cmd.parameters)
                name = mentions.get(cmd.qualified_name, f"/{cmd.qualified_name}")
                embed.add_field(name=f"/{cmd.qualified_name} {params}".strip(),
                                value=f"{name}\n{cmd.description}", inline=False)
            for name, desc in section.get("extra", []):
                embed.add_field(name=name, value=desc, inline=False)
            embeds.append(embed)

        auto = discord.Embed(title="自動解析網址",
                             description="直接在聊天貼上網址，機器人會自動回覆預覽。管理員可用 /解析網頁開關 關閉個別網站。",
                             color=0x2ECC71)
        auto.add_field(name="一般", value="巴哈姆特場外、Facebook、Mobile01", inline=False)
        if is_nsfw:
            auto.add_field(name="NSFW", value="nhentai、wnacg、禁漫天堂、E-Hentai、ExHentai、kemono、coomer、hitomi、missav、jable、supjav、hanime1、iwara、xvideos、pornhub", inline=False)
        auto.add_field(name="右鍵選單（應用程式）",
                       value="**刪除訊息**：刪除此機器人的訊息\n**跳轉頁數**：在本子預覽中跳到指定頁", inline=False)
        embeds.append(auto)

        await interaction.followup.send(embeds=embeds[:10], ephemeral=True)


    @app_commands.command(name="歡迎訊息", description="設定歡迎訊息(會在設定該指令的地方發出)")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.guild_only()
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