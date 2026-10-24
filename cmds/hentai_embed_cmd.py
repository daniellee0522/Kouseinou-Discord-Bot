from discord.ext import commands
from discord import app_commands, Embed
from core.classes import Cog_Extension
from pathlib import Path
from functions.nhentai import test_embed, NumberView
from functions.wnacg import create_wnacg_embed, NumberView2
from functions.jm import jm_embed_async, NumberView3
from functions.ehentai import parse_cookie_text, check_exhentai_cookies, parse_gallery_input, ehentai_embed, EHentaiView
from functions.cdn_pages import cdn_files, reply_with_send
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
            await interaction.response.send_message("你沒有權限使用此指令", ephemeral=True)
        else:
            dict_ = {"cf_clearance": cf_clearance, "csrftoken": csrftoken}
            with open(config.DATA_DIR / 'cookies.json', 'w', encoding='utf8') as f:
                json.dump(dict_, f, ensure_ascii=False, indent=4)
            await interaction.response.send_message("已更新 cookies", ephemeral=True)

    @app_commands.command(name="excookies", description="更新 ExHentai 登入 cookies（僅限機器人擁有者）")
    @app_commands.describe(cookie="在 exhentai.org 從瀏覽器複製的 Cookie 字串（要有 ipb_member_id、ipb_pass_hash）",
                           clear="清除已設定的 cookies，改回只用 e-hentai")
    @app_commands.default_permissions(administrator=True)
    async def excookies(self, interaction: discord.Interaction, cookie: str = "", clear: bool = False):
        if interaction.user.id != config.OWNER_ID:
            await interaction.response.send_message("你沒有權限使用此指令", ephemeral=True)
            return
        if clear:
            cookies = {}
        else:
            cookies = parse_cookie_text(cookie)
            if not {"ipb_member_id", "ipb_pass_hash"} <= cookies.keys():
                await interaction.response.send_message("找不到 ipb_member_id 和 ipb_pass_hash，請貼上完整的 Cookie 字串", ephemeral=True)
                return
            await interaction.response.defer(ephemeral=True)
            cookies = await check_exhentai_cookies(self.bot.session, cookies)
            if cookies is None:
                await interaction.followup.send("這組 cookies 登入不了 exhentai（可能過期或帳號沒有權限），沒有儲存", ephemeral=True)
                return
        # 存回 token.json（重開後也有效），並直接套用到執行中的 bot
        async with self.bot.data_lock:
            with open(config.DATA_DIR / 'token.json', 'r', encoding='utf8') as f:
                data = json.load(f)
            data["exhentai_cookies"] = cookies
            with open(config.DATA_DIR / 'token.json', 'w', encoding='utf8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        config.EXHENTAI_COOKIES = cookies
        text = "已清除 ExHentai cookies" if clear else f"已更新 ExHentai cookies（{'、'.join(cookies)}）"
        if interaction.response.is_done():
            await interaction.followup.send(text, ephemeral=True)
        else:
            await interaction.response.send_message(text, ephemeral=True)


    @app_commands.command(name="wnacg", description="回傳wnacg embed")
    @app_commands.describe(digit="神秘數字")
    async def wnacg(self, interaction: discord.Interaction, digit: int):
        digit = str(digit)

        async def work():
            embed = await create_wnacg_embed(session=self.bot.session, digit=digit, cdn=getattr(self.bot, 'image_cdn', None))
            if embed == 404:
                return dict(content="不存在")
            if embed == 403:
                return dict(content="存取遭拒")
            return dict(embed=embed, view=NumberView2(session=self.bot.session, embed=embed), **cdn_files(embed))

        # 2 秒內備妥就一次回覆，不必先 defer 再 followup
        await reply_with_send(interaction, work)


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

        async def work():
            try:
                embed = await jm_embed_async(url, cdn=getattr(self.bot, 'image_cdn', None))
            except Exception:
                return dict(content="不存在或存取遭拒")
            return dict(embed=embed, view=NumberView3(embed=embed), **cdn_files(embed))

        await reply_with_send(interaction, work)
            

    # 不用 nsfw=True：Discord 會把年齡限制指令從 bot 的指令清單藏起來，改成執行時檢查頻道
    @app_commands.command(name="ehentai", description="回傳 E-Hentai / ExHentai embed（限 NSFW 頻道）")
    @app_commands.describe(gallery="本子編號（例如 4275260）、本子或單頁網址，或「gid token」",
                           page="從第幾頁開始（預設第 1 頁；單頁網址會用網址上的頁碼）")
    async def ehentai(self, interaction: discord.Interaction, gallery: str, page: app_commands.Range[int, 1] = None):
        channel = interaction.channel
        if isinstance(channel, discord.Thread):
            channel = channel.parent
        if interaction.guild is not None and not (channel and getattr(channel, "is_nsfw", lambda: False)()):
            return await interaction.response.send_message("這個指令只能在 NSFW 頻道或私訊使用。", ephemeral=True)

        async def work():
            try:
                parsed = await parse_gallery_input(self.bot.session, gallery)
            except Exception:
                parsed = None
            if parsed is None:
                return dict(content="找不到這個本子。請輸入本子編號、e-hentai / exhentai 網址或「gid token」；已被刪除的本子要貼完整網址", ephemeral=True)
            gid, token, link_page, ex = parsed
            try:
                embed, pages = await ehentai_embed(self.bot.session, gid, token, page or link_page or 1,
                                                   cdn=getattr(self.bot, 'image_cdn', None), ex=ex)
            except Exception:
                embed = None
            if embed is None:
                return dict(content="不存在或存取遭拒")
            view = EHentaiView(session=self.bot.session, embed=embed) if pages > 1 else None
            return dict(embed=embed, **({"view": view} if view else {}), **cdn_files(embed))

        await reply_with_send(interaction, work)


    @app_commands.command(name="nhentai", description="回傳nhentai embed")
    @app_commands.describe(digit="神秘數字")
    async def nh(self, interaction: discord.Interaction, digit: int):
        digit = str(digit)
        with open(config.DATA_DIR / 'cookies.json', 'r', encoding='utf8') as file:
            data = json.load(file)
        cf_clearance = data["cf_clearance"]
        csrftoken = data["csrftoken"]
        async def work():
            embed = await test_embed(session=self.bot.session, sec5h= self.bot.missav_crawl,
                digit=digit, cf_clearance=cf_clearance, csrftoken=csrftoken,
                cdn=getattr(self.bot, 'image_cdn', None))
            if embed == 404:
                return dict(content="不存在")
            if embed == 403:
                return dict(content="存取遭拒")
            view = NumberView(embed=embed, session=self.bot.session, sec5h=self.bot.missav_crawl)
            return dict(embed=embed, view=view, **cdn_files(embed))

        # 2 秒內備妥就一次回覆；來不及（例如第一次上傳）才 defer 避免互動逾時
        await reply_with_send(interaction, work)

async def setup(bot):
    await bot.add_cog(HentaiEmbedCmd(bot))