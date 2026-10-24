import discord
from discord import app_commands, Interaction, ui, TextStyle, Message, Embed
import re
from core.classes import Cog_Extension
from functions.wnacg import get_page_image, apply_page, embed_thread_hint, NumberView2
from functions.nhentai import nh_page_image, nh_gallery, extract_numbers, NumberView
from functions.jm import extract_number_from_url, jm_page_image, jm_gallery, JM_COLOR, NumberView3
from functions.kemono import render_kemono_page, KemonoView
from functions.hitomi import render_hitomi_page, HitomiView
from functions.ehentai import render_ehentai_page, EHentaiView
import asyncio
from functions.cdn_pages import apply_page as apply_cdn_page, strip_fragment, edit_attachments, run_within_deadline


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
            if item.name == "頁數":
                page = int(item.value.strip())
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

        if embed.author.name not in ("wnacg", "nhentai", "禁漫天堂", "kemono", "coomer", "hitomi", "E-Hentai", "ExHentai"):
            return await interaction.response.send_message(
                "不支援此 embed 的跳轉頁數功能。", ephemeral=True
            )

        # --- 3. 更新 embed 圖片 ---
        async def work():
            if embed.author.name == "wnacg":
                digit = re.search(r"aid-(\d+)\.html", embed.url).group(1)

                cdn = getattr(self.bot, 'image_cdn', None)
                img = await get_page_image(self.bot.session, cdn, digit, target_page, page=page,
                                           thread_hint=embed_thread_hint(embed), inline=True)
                apply_page(embed, img, target_page, cdn, digit)
                view = NumberView2(session=self.bot.session)
                view.middle_button.label = f"{target_page}/{page}"

            elif embed.author.name == "nhentai":
                cdn = getattr(self.bot, 'image_cdn', None)
                number = extract_numbers(strip_fragment(embed.url))[0]
                img = await nh_page_image(self.bot.session, self.bot.missav_crawl, cdn, number, target_page,
                                          thread_hint=embed_thread_hint(embed), inline=True)
                apply_cdn_page(embed, img, target_page, cdn, nh_gallery(number))
                view = NumberView(session=self.bot.session, sec5h=self.bot.missav_crawl)
                view.middle_button.label = f"{target_page}/{page}"

            elif embed.author.name == "hitomi":
                cdn = getattr(self.bot, 'image_cdn', None)
                await render_hitomi_page(self.bot.session, cdn, embed, target_page)
                img = embed.image.url
                view = HitomiView(session=self.bot.session)
                view.middle_button.label = f"{target_page}/{page}"

            elif embed.author.name in ("E-Hentai", "ExHentai"):
                cdn = getattr(self.bot, 'image_cdn', None)
                await render_ehentai_page(self.bot.session, cdn, embed, target_page)
                img = embed.image.url
                view = EHentaiView(session=self.bot.session)
                view.middle_button.label = f"{target_page}/{page}"

            elif embed.author.name in ("kemono", "coomer"):
                cdn = getattr(self.bot, 'image_cdn', None)
                await render_kemono_page(self.bot.session, cdn, embed, target_page)
                img = embed.image.url
                view = KemonoView(session=self.bot.session)
                view.middle_button.label = f"{target_page}/{page}"

            else:
                cdn = getattr(self.bot, 'image_cdn', None)
                id = extract_number_from_url(strip_fragment(embed.url))
                img = await jm_page_image(cdn, id, target_page, total=page, thread_hint=embed_thread_hint(embed),
                                          inline=True)
                apply_cdn_page(embed, img, target_page, cdn, jm_gallery(id), colour=JM_COLOR)
                view = NumberView3()
                view.middle_button.label = f"{target_page}/{page}"

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


async def setup(bot):
    await bot.add_cog(JumpPage(bot))
