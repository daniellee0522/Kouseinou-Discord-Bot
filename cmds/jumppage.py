import discord
from discord import app_commands, Interaction, ui, TextStyle, Message, Embed
import re
from core.classes import Cog_Extension
from functions.wnacg import find_img_new, NumberView2
from functions.nhentai import get_image_url, extract_numbers, NumberView
from functions.jm import extract_number_from_url, fillnum, NumberView3


# ===== Modal：讓使用者輸入頁數 =====
class JumpPageModal(ui.Modal, title="跳轉頁數"):
    page_input = ui.TextInput(
        label="輸入要跳轉的頁數",
        placeholder="例如：5",
        style=TextStyle.short,
        required=True,
        max_length=5,
    )

    def __init__(self, target_message: Message):
        super().__init__()
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

        # --- 3. 更新 embed 圖片 ---
        img = None
        if embed.author.name == "wnacg":
            digit = re.search(r"aid-(\d+)\.html", embed.url).group(1)
            test = False
            if "TRUE" in embed.image.url.split("?")[-1]:
                match1 = re.search(r'img(\d+)\.qy0\.ru', embed.image.url)
                test = True
                page_num = embed.image.url.split("?")[-2]
            else:
                page_num = embed.image.url.split("?")[-1]

            img = find_img_new(digit=digit, page=page, page_num=target_page, test=test) + "?TRUE"
            if test:
                img = re.sub(r"img(\d+)\.qy0\.ru", match1.group(0), img)
            view = NumberView2()
            view.middle_button.label = f"{target_page}/{page}"

        elif embed.author.name == "nhentai":
            title = embed.url
            number = extract_numbers(title)[0]
            link_lst = get_image_url(number)
            img = link_lst[target_page - 1]
            view = NumberView()
            view.middle_button.label = f"{target_page}/{page}"
        
        elif embed.author.name == "禁漫天堂":
            title = embed.url
            id = extract_number_from_url(title)
            img = f"https://cdn-msp.18comic.org/media/photos/{id}/{fillnum(target_page)}.webp"
            view = NumberView3()
            view.middle_button.label = f"{target_page}/{page}"


        else:
            return await interaction.response.send_message(
                "不支援此 embed 的跳轉頁數功能。", ephemeral=True
            )

        if img:
            embed.set_image(url=img)
            await self.target_message.edit(embed=embed, view=view)

        await interaction.response.send_message(
            f"已跳轉到第 {target_page} 頁。", ephemeral=True
        )


# ===== Cog：右鍵選單 =====
class JumpPage(Cog_Extension):
    def __init__(self, bot):
        self.bot = bot

        # --- 動態註冊 context menu ---
        @app_commands.context_menu(name="跳轉頁數")
        async def jump_page_menu(interaction: Interaction, message: Message):
            # 1. 確認是你的機器人發出的訊息
            if message.author.id != interaction.client.user.id:
                return await interaction.response.send_message(
                    "只能操作機器人自己的訊息。", ephemeral=True
                )

            # 2. 必須有 embed
            if not message.embeds:
                return await interaction.response.send_message(
                    "這個訊息沒有 embed。", ephemeral=True
                )

            # 3. 彈出 Modal
            modal = JumpPageModal(message)
            await interaction.response.send_modal(modal)

        self.bot.tree.add_command(jump_page_menu)


async def setup(bot):
    await bot.add_cog(JumpPage(bot))
