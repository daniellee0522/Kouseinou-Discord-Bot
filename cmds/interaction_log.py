# 把機器人觸發的互動記到 log 頻道（token.json 的 log_channel_id，0 = 不記）：
# 網址解析、關鍵字（抽卡）、斜線指令／右鍵選單、$ 指令、按鈕與跳頁視窗。
# 伺服器多、訊息量大，逐筆送會撞到 Discord 的速率限制：先排進佇列，每 FLUSH_SECONDS 秒合併成幾則訊息送出。
import asyncio
import time

import discord
from discord.ext import commands

import config

FLUSH_SECONDS = 5
MAX_MESSAGE_CHARS = 1900
NO_MENTIONS = discord.AllowedMentions.none()


def _who(user) -> str:
    return f"{discord.utils.escape_markdown(str(user))} (`{user.id}`)"


def _where(guild, channel) -> str:
    if guild is None:
        return "私訊"
    name = getattr(channel, "name", None)
    return f"{discord.utils.escape_markdown(guild.name)} / #{name}" if name else discord.utils.escape_markdown(guild.name)


def _now() -> str:
    return f"<t:{int(time.time())}:T>"


class InteractionLog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.lines = []
        self.task = None

    @property
    def enabled(self) -> bool:
        return config.LOG_CHANNEL_ID != 0

    async def cog_load(self):
        if self.enabled:
            self.task = asyncio.create_task(self._flush_loop())

    async def cog_unload(self):
        if self.task is not None:
            self.task.cancel()

    def add(self, line: str):
        if self.enabled:
            self.lines.append(f"{_now()} {line}")

    # ---------- 送出 ----------
    async def _flush_loop(self):
        await self.bot.wait_until_ready()
        while True:
            await asyncio.sleep(FLUSH_SECONDS)
            try:
                await self.flush()
            except Exception as e:  # log 頻道出問題不影響其他功能
                print(f"[interaction_log] flush failed: {e!r}")

    async def flush(self):
        if not self.lines:
            return
        lines, self.lines = self.lines, []
        channel = self.bot.get_channel(config.LOG_CHANNEL_ID) or await self.bot.fetch_channel(config.LOG_CHANNEL_ID)
        chunk = ""
        for line in lines:
            line = line[:MAX_MESSAGE_CHARS]
            if chunk and len(chunk) + len(line) + 1 > MAX_MESSAGE_CHARS:
                await channel.send(chunk, allowed_mentions=NO_MENTIONS, suppress_embeds=True)
                chunk = ""
            chunk = f"{chunk}\n{line}" if chunk else line
        if chunk:
            await channel.send(chunk, allowed_mentions=NO_MENTIONS, suppress_embeds=True)

    # ---------- 網址解析、關鍵字（由 events.py dispatch） ----------
    @commands.Cog.listener()
    async def on_link_parsed(self, message, name, url, error=None):
        status = f"❌ `{type(error).__name__}: {str(error)[:150]}`" if error else "✅"
        self.add(f"🔗 {status} **{name}** <{url}>｜{_who(message.author)}｜{_where(message.guild, message.channel)}"
                 f"｜{message.jump_url}")

    @commands.Cog.listener()
    async def on_keyword_triggered(self, message, name):
        self.add(f"🎰 **{name}**｜{_who(message.author)}｜{_where(message.guild, message.channel)}｜{message.jump_url}")

    # ---------- 斜線指令、右鍵選單、$ 指令 ----------
    @commands.Cog.listener()
    async def on_app_command_completion(self, interaction: discord.Interaction, command):
        options = " ".join(f"{k}=`{v}`" for k, v in interaction.namespace)
        if isinstance(command, discord.app_commands.ContextMenu):
            label = f"右鍵選單「{command.name}」"
        else:
            label = f"/{command.qualified_name}"
        self.add(f"⌨️ **{label}** {options}｜{_who(interaction.user)}｜{_where(interaction.guild, interaction.channel)}")

    @commands.Cog.listener()
    async def on_command_completion(self, ctx: commands.Context):
        self.add(f"⌨️ **${ctx.command.qualified_name}**｜{_who(ctx.author)}｜{_where(ctx.guild, ctx.channel)}")

    # ---------- 按鈕、跳頁視窗 ----------
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type not in (discord.InteractionType.component, discord.InteractionType.modal_submit):
            return
        data = interaction.data or {}
        custom_id = data.get("custom_id", "")
        message = interaction.message
        # 哪一站：翻頁訊息的 embed 作者名稱（nhentai、wnacg、kemono…）
        site = message.embeds[0].author.name if message and message.embeds and message.embeds[0].author else None
        if interaction.type == discord.InteractionType.modal_submit:
            values = [c.get("value") for row in data.get("components", []) for c in row.get("components", [])]
            what = f"📝 跳頁視窗 `{'、'.join(v for v in values if v)}`"
        else:
            what = f"🔘 按鈕「{self._button_label(message, custom_id)}」"
        jump = f"｜{message.jump_url}" if message else ""
        self.add(f"{what}{f' [{site}]' if site else ''}｜{_who(interaction.user)}"
                 f"｜{_where(interaction.guild, interaction.channel)}{jump}")

    @staticmethod
    def _button_label(message, custom_id) -> str:
        """從訊息上的元件找出按鈕顯示的文字（<<、>、刷新影片…）；找不到就用 custom_id"""
        for row in getattr(message, "components", None) or []:
            for item in getattr(row, "children", []):
                if getattr(item, "custom_id", None) == custom_id:
                    return item.label or str(item.emoji or custom_id)
        return custom_id


async def setup(bot):
    await bot.add_cog(InteractionLog(bot))
