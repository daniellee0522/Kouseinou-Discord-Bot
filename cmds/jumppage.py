import discord
from discord import app_commands, Interaction, ui, TextStyle, Message, Embed
import re
from core.classes import Cog_Extension
from functions.page_render import PAGED_SITES, render_page
import asyncio
from functions.cdn_pages import edit_attachments, run_within_deadline


# ===== Modal：讓使用者輸入頁數 =====
class JumpPageModal(ui.Modal, title="跳轉頁數"):
    page_input = ui.TextInput(
        label="輸入要跳轉的頁數",
        placeholder="例如：5",
        style=TextStyle.short,
        required=True,
        max_length=5,
    )

    def __init__(self, bot, target_message: Message):
        super().__init__()
        self.bot = bot
        self.target_message = target_message

    async def on_submit(self, interaction: Interaction):
        embed = self.target_message.embeds[0]
        page = None

        for item in embed.fields:
            if item.name == "頁數" and str(item.value).strip().isdigit():
                page = int(str(item.value).strip())
                break
        # --- 1. 驗證是否為數字 ---
        try:
            target_page = int(self.page_input.value)
        except ValueError:
            return await interaction.response.send_message(
                "請輸入合法的整數頁數。", ephemeral=True
            )
        
        if not page:
            return await interaction.response.send_message(
                "找不到頁數資訊。", ephemeral=True
            )
        
        # --- 2. 檢查頁數範圍 ---
        if target_page < 1 or target_page > page:
            return await interaction.response.send_message(
                f"頁數需介於 1 到 {page} 之間。", ephemeral=True
            )

        if embed.author.name not in PAGED_SITES:
            return await interaction.response.send_message(
                "不支援此 embed 的跳轉頁數功能。", ephemeral=True
            )

        # --- 3. 更新 embed 圖片 ---
        async def work():
            img, view = await render_page(self.bot, embed, target_page)
            return dict(embed=embed, view=view, attachments=edit_attachments(embed)) if img else None

        # 2 秒內備妥就直接回覆（省一次 defer）；更新訊息與回覆確認同時送出
        kwargs, deferred = await run_within_deadline(interaction, work, ephemeral=True)
        confirm = f"已跳轉到第 {target_page} 頁。"
        jobs = [interaction.followup.send(confirm, ephemeral=True) if deferred
                else interaction.response.send_message(confirm, ephemeral=True)]
        if kwargs:
            jobs.insert(0, self.target_message.edit(**kwargs))
        await asyncio.gather(*jobs)


# ===== Cog：右鍵選單 =====
class JumpPage(Cog_Extension):
    def __init__(self, bot):
        super().__init__(bot)

        @app_commands.context_menu(name="跳轉頁數")
        async def jump_page_menu(interaction: Interaction, message: Message):
            if message.author.id != interaction.client.user.id:
                return await interaction.response.send_message(
                    "只能操作機器人自己的訊息。", ephemeral=True
                )
            if not message.embeds:
                return await interaction.response.send_message(
                    "這個訊息沒有 embed。", ephemeral=True
                )
            modal = JumpPageModal(bot, message)
            await interaction.response.send_modal(modal)

        self.jump_page_menu = jump_page_menu
        bot.tree.add_command(jump_page_menu)

    async def cog_unload(self):
        self.bot.tree.remove_command(self.jump_page_menu.name, type=self.jump_page_menu.type)


async def setup(bot):
    await bot.add_cog(JumpPage(bot))
