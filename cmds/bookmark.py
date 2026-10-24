# 書籤：右鍵「加入書籤」把本子 embed 目前那頁私訊給使用者，之後在私訊裡繼續翻頁，書籤就跟著停在最新頁。
# 不存在本機：書籤就是機器人私訊給使用者、內容以 MARK 開頭的訊息。
# 查詢＝讀私訊紀錄；刪除＝列表上的刪除鈕，或在私訊裡對書籤按右鍵「刪除訊息」。
# 列表：discord.py 2.6 以上用新版元件（Components V2）做成卡片，刪除鈕在卡片裡、站名前面有網站圖示；
# 舊版 discord.py 沒有卡片元件，退回 embed 列表＋下方一排刪除鈕。
import asyncio
import re

import discord
from discord import app_commands

from discord.ext import commands

from core.classes import Cog_Extension
from functions.app_emoji import app_emojis
from functions.brand import MISSAV, JABLE, SUPJAV
from functions.ehentai import EHENTAI, EXHENTAI
from functions.hanime1 import HANIME1
from functions.hitomi import HITOMI
from functions.iwara import IWARA
from functions.kemono import SITES as KEMONO_SITES
from functions.mobile01 import MOBILE01
from functions.cdn_pages import current_page, total_pages, strip_fragment, edit_attachments, run_within_deadline
from functions.discord_cdn import thread_id_from_url
from functions.page_render import is_paged, render_page, paging_view

MARK = "🔖 書籤"
# 往回讀多少則私訊找書籤
HISTORY_LIMIT = 500
# 列表一頁幾個書籤（每個一張 embed＋一顆刪除鈕）
PER_PAGE = 5
VIDEO_LINK = re.compile(r"\[▶ (?P<name>[^\]]+)\]\((?P<url>https?://[^\s)]+/p/(?P<site>\w+)/(?P<vid>[^\s/?)]+)[^\s)]*)\)")
MESSAGE_LINK = re.compile(r"discord(?:app)?\.com/channels/(\d+|@me)/(\d+)/(\d+)")
HOW_TO_ADD = "對機器人的本子訊息按右鍵 → 應用程式 → **加入書籤**"
# 圖片網址不會過期的站：書籤直接沿用原本的圖，不用重抓
STABLE_IMAGE_SITES = ("kemono", "coomer")
HAS_CARDS = hasattr(discord.ui, "LayoutView")
# 卡片裡的網站圖示用機器人的應用程式表情（存在 Discord 上）；表情名稱只能用英數與底線
SITE_EMOJI_NAMES = {"禁漫天堂": "site_jm"}
# 啟動時先把這些站的圖示建好，第一次看列表就有圖示（其他站第一次出現時才在背景建立）
KNOWN_SITE_ICONS = {
    "nhentai": "https://i.imgur.com/LslnmKV.png",
    "wnacg": "https://i.imgur.com/tZ3fqmm.jpeg",
    "禁漫天堂": "https://i.imgur.com/dYVERFN.png",
    **{site["name"]: site["icon_url"] for site in (EHENTAI, EXHENTAI, HITOMI, HANIME1, IWARA, MOBILE01,
                                                    MISSAV, JABLE, SUPJAV, *KEMONO_SITES.values())},
}


# /書籤 列表 的網站篩選選項（固定選單，不用先讀私訊）
SITE_CHOICES = list(KNOWN_SITE_ICONS) + ["Facebook"]


def _gallery_key(embed: discord.Embed):
    """同一本書只留一個書籤：用 embed 網址（去掉圖床索引）辨識"""
    return strip_fragment(embed.url) or embed.title


def _video(message: discord.Message):
    """hanime1 / iwara 的影片預覽：bot 只貼 host.py 預覽頁的連結，卡片是 Discord 自己依連結產生的"""
    return VIDEO_LINK.search(message.content or "")


def _key(message: discord.Message):
    video = _video(message)
    # 預熱前後的預覽頁網址參數不同（thumb=1／w=1），用站名＋影片 ID 辨識同一部
    return f"video:{video['site']}/{video['vid']}" if video else _gallery_key(message.embeds[0])


def _card(message: discord.Message) -> discord.Embed:
    """書籤的顯示資訊（標題、站名、圖示、縮圖、頁數）。一般預覽就是 bot 自己的 embed；
    影片預覽改從連結文字取站名、用已知的網站圖示，標題與縮圖取自 Discord 產生的卡片"""
    video = _video(message)
    if not video:
        return message.embeds[0]
    unfurl = message.embeds[0] if message.embeds else None
    title = None
    if unfurl:
        title = unfurl.title or re.sub(r"[*_`>#]", "", (unfurl.description or "").strip().split("\n")[0])
    card = discord.Embed(title=(title or f"{video['name']} 影片")[:256], url=video["url"],
                         colour=unfurl.colour if unfurl else None)
    card.set_author(name=video["name"], icon_url=KNOWN_SITE_ICONS.get(video["name"]))
    image = unfurl and ((unfurl.image and unfurl.image.url) or (unfurl.thumbnail and unfurl.thumbnail.url))
    if image:
        card.set_image(url=image)
    return card


def _title(embed: discord.Embed, limit=80):
    return (embed.title or "（無標題）")[:limit]


def _site(embed: discord.Embed):
    return embed.author.name if embed.author and embed.author.name else "預覽"


def _page_text(embed: discord.Embed):
    return f"第 {current_page(embed)}/{total_pages(embed)} 頁" if is_paged(embed) else ""


def _describe(embed: discord.Embed):
    return "・".join(filter(None, (_site(embed), _page_text(embed))))


def _site_emoji_name(site):
    if site in SITE_EMOJI_NAMES:
        return SITE_EMOJI_NAMES[site]
    name = re.sub(r"[^a-z0-9]", "", site.lower())
    return f"site_{name}"[:32] if name else None


def _image_is_stable(embed: discord.Embed, message: discord.Message):
    """原訊息的圖能不能直接沿用：圖床討論串裡的附件（Discord 會自動換新簽章）或網址不會過期的站。
    直接附在原訊息上的第一頁不算：原訊息被刪掉圖就跟著不見。"""
    if embed.author.name in STABLE_IMAGE_SITES:
        return True
    image_url = embed.image.url if embed.image else None
    thread_id = thread_id_from_url(image_url)
    return thread_id is not None and thread_id != message.channel.id


async def _reply(interaction: discord.Interaction, work):
    """FAST_REPLY 內備妥就直接回覆（省一次 defer），否則先 defer 再 followup。回覆都只有本人看得到。"""
    kwargs, deferred = await run_within_deadline(interaction, work, ephemeral=True)
    if deferred:
        await interaction.followup.send(ephemeral=True, **kwargs)
    else:
        await interaction.response.send_message(ephemeral=True, **kwargs)


def _list_embeds(items, page):
    """列表第 page 頁（從 0 開始）：每個書籤一張 embed，作者欄沿用原站名稱與圖示，縮圖是目前那頁"""
    embeds = []
    for index, m in enumerate(items[page * PER_PAGE:(page + 1) * PER_PAGE], page * PER_PAGE + 1):
        source = _card(m)
        embed = discord.Embed(title=f"{index}. {_title(source, 200)}", url=m.jump_url,
                              description=f"{_describe(source)}・加入於 <t:{int(m.created_at.timestamp())}:d>",
                              color=source.colour or 0xF1C40F)
        if source.author and source.author.name:
            embed.set_author(name=source.author.name, icon_url=source.author.icon_url)
        if source.image and source.image.url:
            embed.set_thumbnail(url=source.image.url)
        embeds.append(embed)
    return embeds


class _ListPaging:
    """兩種列表共用：目前頁、刪除後重畫"""

    def _setup(self, cog, user, items, page, label):
        self.cog, self.user, self.items, self.label = cog, user, items, label
        self.pages = max(1, -(-len(items) // PER_PAGE))
        self.page = max(0, min(page, self.pages - 1))
        start = self.page * PER_PAGE
        return enumerate(items[start:start + PER_PAGE], start + 1)

    def _nav_buttons(self):
        buttons = []
        for label, step, disabled in (("◀", -1, self.page == 0), (f"{self.page + 1}/{self.pages}", 0, True),
                                      ("▶", 1, self.page >= self.pages - 1)):
            button = discord.ui.Button(label=label, style=discord.ButtonStyle.gray, disabled=disabled)
            button.callback = self._turn_callback(step)
            buttons.append(button)
        return buttons

    def _delete_button(self, message, **kwargs):
        button = discord.ui.Button(style=discord.ButtonStyle.secondary, **kwargs)
        button.callback = self._delete_callback(message)
        return button

    def _turn_callback(self, step):
        async def callback(interaction: discord.Interaction):
            view = type(self)(self.cog, self.user, self.items, self.page + step, self.label)
            await interaction.response.edit_message(**view.message_kwargs())
        return callback

    def _delete_callback(self, message):
        async def callback(interaction: discord.Interaction):
            try:
                await message.delete()
            except discord.NotFound:
                pass  # 已經在私訊裡刪掉了
            items = [m for m in self.items if m.id != message.id]
            view = type(self)(self.cog, self.user, items, self.page, self.label)
            await interaction.response.edit_message(**view.message_kwargs())
        return callback


class BookmarkListView(_ListPaging, discord.ui.View):
    """舊版 discord.py：embed 列表，下方每個書籤一顆刪除鈕，超過一頁有上下頁"""

    def __init__(self, cog, user, items, page=0, label=None):
        super().__init__(timeout=600)
        for index, m in self._setup(cog, user, items, page, label):
            self.add_item(self._delete_button(m, label=f"刪除 {index}", row=0))
        if self.pages > 1:
            for button in self._nav_buttons():
                button.row = 1
                self.add_item(button)

    def message_kwargs(self):
        if not self.items:
            return dict(content=f"書籤都刪光了。{HOW_TO_ADD}。", embeds=[], view=None)
        return dict(content=f"🔖 **我的書籤{'・' + self.label if self.label else ''}**（{len(self.items)}）點標題跳到私訊裡的書籤，在那裡可以繼續翻頁",
                    embeds=_list_embeds(self.items, self.page), view=self)


if HAS_CARDS:
    class BookmarkCardsView(_ListPaging, discord.ui.LayoutView):
        """新版元件：每個書籤一張卡片（站名＋圖示、標題連到私訊裡的書籤、頁數、目前那頁縮圖），刪除鈕在卡片裡"""

        def __init__(self, cog, user, items, page=0, label=None):
            super().__init__(timeout=600)
            entries = list(self._setup(cog, user, items, page, label))
            if not items:
                self.add_item(discord.ui.TextDisplay(f"書籤都刪光了。{HOW_TO_ADD}。"))
                return
            self.add_item(discord.ui.TextDisplay(f"## 🔖 我的書籤{'・' + label if label else ''}（{len(items)}）\n-# 點標題跳到私訊裡的書籤，在那裡可以繼續翻頁"))
            for index, m in entries:
                source = _card(m)
                site = _site(source)
                emoji = cog.site_emoji(site, source.author.icon_url if source.author else None)
                title = _title(source, 150).replace("[", "［").replace("]", "］")  # 半形括號會弄壞連結
                info = "・".join(filter(None, (_page_text(source), f"加入於 <t:{int(m.created_at.timestamp())}:d>")))
                text = f"{emoji + ' ' if emoji else ''}**{site}**\n### {index}. [{title}]({m.jump_url})\n{info}"
                image = source.image.url if source.image and source.image.url else None
                body = discord.ui.Section(text, accessory=discord.ui.Thumbnail(image)) if image else discord.ui.TextDisplay(text)
                delete = self._delete_button(m, label="刪除書籤")
                self.add_item(discord.ui.Container(body, discord.ui.ActionRow(delete),
                                                   accent_colour=source.colour or 0xF1C40F))
            if self.pages > 1:
                self.add_item(discord.ui.ActionRow(*self._nav_buttons()))

        def message_kwargs(self):
            # 新版元件的訊息不能有 content／embeds
            return dict(view=self)

    ListView = BookmarkCardsView
else:
    ListView = BookmarkListView


class Bookmark(Cog_Extension):
    書籤 = app_commands.Group(name="書籤", description="查詢、新增私訊裡的本子書籤")

    def __init__(self, bot):
        super().__init__(bot)
        self._scans = {}       # user_id -> 讀私訊中的 Task（同一個人同時只讀一次）
        self._tasks = set()  # 背景工作（刪舊書籤、建網站圖示），留住參照避免被回收

        @app_commands.context_menu(name="加入書籤")
        async def bookmark_menu(interaction: discord.Interaction, message: discord.Message):
            await self._add(interaction, message)

        self.bookmark_menu = bookmark_menu
        bot.tree.add_command(bookmark_menu)

    async def cog_unload(self):
        self.bot.tree.remove_command(self.bookmark_menu.name, type=self.bookmark_menu.type)

    # ---------- 書籤清單 ----------
    async def _bookmarks(self, user):
        """使用者私訊裡的書籤訊息，新的在前（每次都重讀，頁數才是最新的）"""
        task = self._scans.get(user.id)
        if task is None:
            task = self._scans[user.id] = asyncio.ensure_future(self._scan(user))
            task.add_done_callback(lambda _: self._scans.pop(user.id, None))
        return await asyncio.shield(task)

    async def _scan(self, user):
        channel = user.dm_channel or await user.create_dm()
        items = [m async for m in channel.history(limit=HISTORY_LIMIT)
                 if m.author.id == self.bot.user.id and m.content.startswith(MARK) and (m.embeds or _video(m))]
        return items

    def _background(self, coro):
        task = asyncio.ensure_future(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def site_emoji(self, site, icon_url):
        """卡片裡站名前的圖示（應用程式表情）。已知網站還沒有的話在背景建立，這次先不顯示、下次列表就有。"""
        name = _site_emoji_name(site)
        store = app_emojis(self.bot)
        if not name or not store.available:
            return None
        emoji = store.get(name)
        # 只替已知的網站建圖示：作者欄可能是上傳者名稱之類的（例如影片卡片），不要每個都建一個表情
        if emoji is None and site in KNOWN_SITE_ICONS:
            self._background(store.ensure(name, KNOWN_SITE_ICONS[site]))
        return emoji

    @commands.Cog.listener()
    async def on_ready(self):
        """已知網站的圖示啟動時就建好，第一次看列表就有圖示"""
        store = app_emojis(self.bot)
        for site, icon_url in KNOWN_SITE_ICONS.items():
            name = _site_emoji_name(site)
            if name:
                await store.ensure(name, icon_url)  # 依序建，避免一次打太多 API

    async def _delete_quietly(self, messages):
        for m in messages:
            try:
                await m.delete()
            except discord.HTTPException:
                pass

    # ---------- 新增 ----------
    async def _add(self, interaction: discord.Interaction, message: discord.Message):
        # 預覽的 embed 一定連到原網頁；抽卡結果、PU 展示卡、統計之類沒有連結的不算
        is_preview = bool(_video(message) or (message.embeds and message.embeds[0].url))
        if message.author.id != self.bot.user.id or not is_preview:
            return await interaction.response.send_message("只能把機器人的網址預覽加入書籤。", ephemeral=True)
        user = interaction.user
        if message.guild is None:
            return await self._mark_in_dm(interaction, message)

        video = _video(message)

        async def work():
            # 讀私訊找舊書籤跟準備這頁的圖同時進行
            scan = asyncio.ensure_future(self._bookmarks(user))
            content = f"{MARK}｜[原訊息]({message.jump_url})"
            embed, view, files = None, None, []
            if video:
                # 重新貼一次預覽頁連結，Discord 會在私訊裡產生一樣能直接播的卡片；
                # 影片太大時原訊息有「到原站觀看」的連結按鈕，一起帶過去
                content += f"\n{video.group(0)}"
                if message.components:
                    view = discord.ui.View.from_message(message, timeout=None)
            else:
                embed = discord.Embed.from_dict(message.embeds[0].to_dict())
            if embed is not None and is_paged(embed):
                if _image_is_stable(embed, message):
                    view = paging_view(self.bot, embed)
                else:
                    # 圖會過期（或附在原訊息上），重新取一次這頁，書籤裡的圖才不會壞掉
                    page = current_page(embed)
                    try:
                        ok, view = await render_page(self.bot, embed, page)
                    except Exception as e:
                        print(f"[bookmark] render {embed.url} page {page} failed: {e!r}", flush=True)
                        ok = False
                    if ok:
                        files = edit_attachments(embed)
                    else:
                        embed = discord.Embed.from_dict(message.embeds[0].to_dict())
                        view = paging_view(self.bot, embed)

            key = _key(message)
            existing = [m for m in await scan if _key(m) == key]
            try:
                sent = await user.send(content=content, files=files,
                                       **({"embed": embed} if embed else {}), **({"view": view} if view else {}))
            except discord.Forbidden:
                return dict(content="沒辦法私訊你：請在伺服器的隱私設定開啟「允許來自伺服器成員的私人訊息」。")
            # 舊書籤在背景刪，不用等
            self._background(self._delete_quietly([m for m in existing if m.id != sent.id]))
            verb = "更新" if existing else "加入"
            card = embed or _card(message)
            return dict(content=f"已{verb}書籤：**{_title(card)}**（{_describe(card)}）\n{sent.jump_url}")

        await _reply(interaction, work)

    async def _mark_in_dm(self, interaction: discord.Interaction, message: discord.Message):
        """私訊裡的預覽本來就在私訊了：不再發一次，直接把這則標成書籤"""
        embed = _card(message)
        if message.content.startswith(MARK):
            return await interaction.response.send_message(f"這則已經是書籤了（{_describe(embed)}）。", ephemeral=True)

        async def work():
            existing = [m for m in await self._bookmarks(interaction.user)
                        if _key(m) == _key(message) and m.id != message.id]
            # 只改文字，embed 和翻頁按鈕不動
            await message.edit(content=f"{MARK}｜{message.content}" if message.content else MARK)
            self._background(self._delete_quietly(existing))
            note = "，同一本的舊書籤已移除" if existing else ""
            return dict(content=f"已將這則訊息設為書籤{note}：**{_title(embed)}**（{_describe(embed)}）")

        await _reply(interaction, work)

    @書籤.command(name="新增", description="用訊息連結把機器人的預覽訊息加入書籤")
    @app_commands.describe(連結="訊息連結（對訊息按右鍵 → 複製訊息連結）")
    async def add_by_link(self, interaction: discord.Interaction, 連結: str):
        match = MESSAGE_LINK.search(連結)
        if not match:
            return await interaction.response.send_message(f"這不是訊息連結。也可以直接{HOW_TO_ADD}。", ephemeral=True)
        guild_id, channel_id, message_id = match.groups()
        not_found = "找不到這則訊息，或你沒有權限看它。"
        try:
            channel = self.bot.get_channel(int(channel_id)) or await self.bot.fetch_channel(int(channel_id))
            # 只能收藏自己看得到的訊息（機器人看得到不代表使用者看得到）
            if guild_id != "@me":
                member = channel.guild.get_member(interaction.user.id) or await channel.guild.fetch_member(interaction.user.id)
                if not channel.permissions_for(member).read_message_history:
                    return await interaction.response.send_message(not_found, ephemeral=True)
            elif getattr(channel, "recipient", None) != interaction.user:
                return await interaction.response.send_message(not_found, ephemeral=True)
            message = await channel.fetch_message(int(message_id))
        except (discord.HTTPException, AttributeError):  # NotFound、Forbidden 都是 HTTPException
            return await interaction.response.send_message(not_found, ephemeral=True)
        await self._add(interaction, message)

    # ---------- 查詢 ----------
    @書籤.command(name="列表", description="列出你的書籤，可以直接按鈕刪除")
    @app_commands.describe(網站="只看某個網站的書籤")
    @app_commands.choices(網站=[app_commands.Choice(name=site, value=site) for site in SITE_CHOICES])
    async def list_bookmarks(self, interaction: discord.Interaction, 網站: app_commands.Choice[str] = None):
        async def work():
            items = await self._bookmarks(interaction.user)
            if not items:
                return dict(content=f"還沒有書籤。{HOW_TO_ADD}。")
            label = 網站.value if 網站 else None
            if label:
                items = [m for m in items if _site(_card(m)) == label]
                if not items:
                    return dict(content=f"沒有 {label} 的書籤。")
            return ListView(self, interaction.user, items, label=label).message_kwargs()

        await _reply(interaction, work)


async def setup(bot):
    await bot.add_cog(Bookmark(bot))
