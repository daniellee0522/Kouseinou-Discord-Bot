import discord
from discord.ext import commands
import re
import traceback
import json
import asyncio
import random
from bs4 import BeautifulSoup
# 導入你原本在 functions 中的解析函數
from functions.embed_permission import is_embed_ban
from functions.slot import Gacha, check_lock, block_check
from functions.jm import jm_embed_async, NumberView3
from functions.cdn_pages import cdn_files
from functions.xvideo import xvideo_embed
from functions.wnacg import create_wnacg_embed, resolve_wnacg_view, NumberView2
from functions.nhentai import test_embed, NumberView
from functions.pornhub import get_pornhub_embed
from functions.supav import chrome_crawl, supjav_crawl
from functions.brand import MISSAV, JABLE
from functions.baha import extract_urls, bahaog, reload_baha_tk, Conf
from functions.gacha import process_gacha_data
from functions.facebook_fetch_new import get_facebook_data
from functions.kemono import kemono_post_embed, kemono_creator_embed, resolve_short_post, KemonoView
from functions.hitomi import hitomi_embed, HitomiView
from functions.ehentai import ehentai_embed, resolve_page_link, EHentaiView
from functions.mobile01 import mobile01_embeds
from functions.hanime1 import hanime1_embed
from functions.iwara import iwara_embed, iwara_image_embed
from functions.video_refresh import fetch_video_info, preview_url, warm_video
import aiohttp
import config

# ... 其他解析函數
sac_bh = Conf('sacPY')

class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # 定義網址與對應處理函數的映射表 (範例)
        self.url_patterns = {
            r'18comic\.(?:vip|org)/(?:album|photo)/(\d+)[^\s]*': self.handler_jm,
            r'wnacg(\.com|\.ru)/photos-view-id-(\d+)[^\s]*': self.handler_wnacg_view,
            r'wnacg(\.com|\.ru)/photos-(?:index|slide|slist|index-page)(?:-\d+)?-aid-(\d+)[^\s]*': self.handler_wnacg,
            r'nhentai\.net/g/(\d+)[^\s]*': self.handler_nhentai,
            r'missav\.(ai|ws)/(\w+)[^\s]*': self.handler_missav,
            r'jable\.tv/videos/([\w-]+)[^\s]*': self.handler_jable,
            r'xvideos\.com/video[^\s]*': self.handler_xvideo,
            r'pornhub\.com/view_video\.php\?viewkey=(\w+)': self.handler_pornhub,
            r'supjav\.com/(?:[a-z]{2}/)?\d+\.html': self.handler_supjav,
            r'forum\.gamer\.com\.tw/.*?bsn=(\d+)[^\s]*': self.handler_baha,
            r'(facebook\.com|fb\.watch)[^\s]*': self.handler_facebook,
            r'(kemono|coomer)\.(?:su|cr|st|party)/(\w+)/user/([\w.-]+)/post/(\d+)': self.handler_kemono,
            r'(kemono|coomer)\.(?:su|cr|st|party)/(\w+)/post/(\d+)': self.handler_kemono_short,
            r'(kemono|coomer)\.(?:su|cr|st|party)/(\w+)/user/([\w.-]+)/?(?![\w./-])': self.handler_kemono_creator,
            r'hitomi\.la/(?:galleries/|reader/|\w+/[^\s]*?-)(\d+)\.html(?:#(\d+))?': self.handler_hitomi,
            r'(e-|ex)hentai\.org/(?:g|mpv)/(\d+)/([0-9a-f]{10})[^\s]*': self.handler_ehentai,
            r'(e-|ex)hentai\.org/s/([0-9a-f]{10})/(\d+)-(\d+)[^\s]*': self.handler_ehentai_page,
            r'mobile01\.com/topicdetail\.php\?[^\s]*?\bt=\d+[^\s]*': self.handler_mobile01,
            r'hanime(?:1|one)\.me/watch\?(?:[^\s]*?&)?v=(\d+)': self.handler_hanime1,
            r'iwara\.tv/video/(\w+)[^\s]*': self.handler_iwara,
            r'iwara\.tv/image/(\w+)[^\s]*': self.handler_iwara_image
        }
        self.keywords_match = {
            r"-1200": self.keyword_handler_gacha
        }
        self._warm_tasks = set()

    def load_data(self,guild_id, num=1, DATA_FILE=None):
        if DATA_FILE is None:
            DATA_FILE = config.DATA_DIR / 'message_count.json'
        if guild_id in config.GUILD_IDS:
            return
        with open(DATA_FILE, "r") as f:
                data = json.load(f)
        if str(guild_id) not in data:
            data[str(guild_id)] = num
        else:
            data[str(guild_id)] += num
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=4)


    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        # 當 bot 加入新的伺服器時更新伺服器數量
        server_count = len(self.bot.guilds)

        # 更新 JSON 數據
        data = {
            "server_count": server_count
        }

        # load_data(guild.id, -1000)

        # 寫入 JSON 文件
        with open(config.DATA_DIR / 'server_count.json', 'w') as json_file:
            json.dump(data, json_file)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        # 當 bot 被踢出或退出伺服器時更新伺服器數量
        server_count = len(self.bot.guilds)

        # 更新 JSON 數據
        data = {
            "server_count": server_count
        }

        # 寫入 JSON 文件
        with open(config.DATA_DIR / 'server_count.json', 'w') as json_file:
            json.dump(data, json_file)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        server_id = str(member.guild.id)
        print("Somebody joined")
        # 替換為你的伺服器中的目標身分組名稱
        role_name = "新人"  
        # 獲取伺服器中的目標身分組
        role = discord.utils.get(member.guild.roles, name=role_name)
        if int(server_id) == 927850351703506954:
            if role is None:
                print(f"找不到身分組 {role_name}，略過分配")
            else:
                try:
                    # 為新成員分配身分組
                    await member.add_roles(role)
                    print(f"已成功為 {member.name} 分配身分組 {role.name}")
                except discord.Forbidden:
                    print(f"無法分配身分組 {role.name}，請檢查權限")
                except discord.HTTPException as e:
                    print(f"發生錯誤：{e}")

        with open(config.DATA_DIR / 'welcome.json', 'r', encoding='utf8') as file:
            data = json.load(file)
        try:
            if server_id in data:
                message = data[server_id][0]
                channel = self.bot.get_channel(data[server_id][1])
                if channel is None:
                    # 歡迎頻道已被刪除或機器人看不到
                    print(f"找不到伺服器 {server_id} 的歡迎頻道")
                    return
                await asyncio.sleep(1)
                await channel.send(message)
            else:
                name = member.guild.name
                await member.send(f"歡迎來到{name}伺服器")
        except discord.HTTPException as e:
            # 頻道沒有發言權限，或成員關閉私訊
            print(f"無法發送歡迎訊息：{e}")

    @commands.Cog.listener()
    async def on_message(self, message):
        process = False
        # 排除機器人自己的訊息
        if message.author.bot:
            return
        
        if block_check(message.channel.id):
            return
        
        for pattern, handler in self.url_patterns.items():
            matches = list(re.finditer(pattern, message.content))
            if matches:
                process = True
                for match in matches:
                    url = "https://" + match.group(0)
                    print(url)
                    # 執行處理函式；結果交給 interaction_log 記到 log 頻道。單一網址出錯不影響其他網址與指令
                    name = handler.__name__.removeprefix("handler_")
                    try:
                        await handler(message, url, match)
                    except Exception as e:
                        traceback.print_exc()
                        self.bot.dispatch("link_parsed", message, name, url, e)
                    else:
                        self.bot.dispatch("link_parsed", message, name, url)

        for pattern, handler in self.keywords_match.items():
            if pattern == message.content:
                await handler(message)
                self.bot.dispatch("keyword_triggered", message, handler.__name__.removeprefix("keyword_handler_"))
                process = True
                break

        await self.bot.process_commands(message)

        
    def is_nsfw_channel(self, channel) -> bool:
        if getattr(channel, "guild", None) is None:
            return True
        if isinstance(channel, discord.Thread):
            channel = channel.parent
        return bool(channel and getattr(channel, "is_nsfw", lambda: False)())

    # --- 各個網址的處理邏輯 ---
    async def handler_jm(self, message, url, match):
        # await message.channel.send(f"偵測到 JM 網址: {url}")
        if message.guild is not None and is_embed_ban(server_id=message.guild.id, arg="jm"):
            return
        url = url.replace("/photo", "/album")
        embed = await jm_embed_async(url, cdn=getattr(self.bot, 'image_cdn', None))
        view = NumberView3(embed=embed)
        await message.channel.send(embed=embed, view=view, **cdn_files(embed))
        await message.edit(suppress=True)


    async def handler_wnacg(self, message, url, match):
        if self.is_nsfw_channel(message.channel) is False:
            return
        if message.guild is not None and is_embed_ban(server_id=message.guild.id, arg="wn"):
            return
        content_id = match.group(2)
        embed = await create_wnacg_embed(self.bot.session, content_id, cdn=getattr(self.bot, 'image_cdn', None))
        if embed not in [404, 403]:
            view = NumberView2(session=self.bot.session, embed=embed)
            await message.channel.send(embed=embed, view=view, **cdn_files(embed))
            await message.edit(suppress=True)


    async def handler_wnacg_view(self, message, url, match):
        if not self.is_nsfw_channel(message.channel):
            return
        # photos-view-id-*.html 是單頁瀏覽連結，view id 跟相簿的 aid 無關，
        # 需要先進去該頁面反查所屬的 aid 與頁碼，才能組出跟 handler_wnacg 一樣的 embed
        if message.guild is not None and is_embed_ban(server_id=message.guild.id, arg="wn"):
            return
        view_id = match.group(2)
        resolved = await resolve_wnacg_view(self.bot.session, view_id)
        if resolved is None:
            return
        digit, page_num, page_src = resolved
        embed = await create_wnacg_embed(self.bot.session, digit, page_num=page_num, cdn=getattr(self.bot, 'image_cdn', None),
                                         first_src=page_src)
        if embed not in [404, 403]:
            view = NumberView2(session=self.bot.session, embed=embed)
            await message.channel.send(embed=embed, view=view, **cdn_files(embed))
            try:
                await message.edit(suppress=True)
            except discord.Forbidden:
                pass

    async def handler_nhentai(self, message, url, match):
        if self.is_nsfw_channel(message.channel) is False:
            return
        if message.guild is not None and is_embed_ban(server_id=message.guild.id, arg="nh"):
            return
        content_id = match.group(1)
        embed = await test_embed(session=self.bot.session, sec5h=self.bot.missav_crawl, digit=content_id, cf_clearance="", csrftoken="",
                                 cdn=getattr(self.bot, 'image_cdn', None))
        view = NumberView(embed=embed, session=self.bot.session, sec5h=self.bot.missav_crawl)
        if embed:
            await message.channel.send(embed=embed, view=view, **cdn_files(embed))
            await message.edit(suppress=True)

    async def handler_xvideo(self, message, url, match):
        if self.is_nsfw_channel(message.channel) is False:
            return
        if message.guild is not None and is_embed_ban(server_id=message.guild.id, arg="andy"):
            return
        embed, video_url = await asyncio.to_thread(xvideo_embed, url)
        if embed:
            await message.channel.send(embed=embed)
            await message.channel.send(f"[.]({video_url})")
            await message.edit(suppress=True)

    async def handler_pornhub(self, message, url, match):
        if self.is_nsfw_channel(message.channel) is False:
            return
        embed = await get_pornhub_embed(url)
        if embed:
            await message.channel.send(embed=embed)
            await message.edit(suppress=True)

    async def handler_missav(self, message, url, match):
        response = await self.bot.missav_crawl.request(url)
        soup = BeautifulSoup(response, 'html.parser')
        description = soup.find('meta', attrs={'name': 'description'})
        title = soup.find('meta', attrs={'property': 'og:title'})
        image = soup.find('meta', attrs={'property': 'og:image'})

        embed = discord.Embed(title=title['content'], url=url, color=MISSAV["color"])
        if image:
            embed.set_image(url=image['content'])
        if description:
            embed.description = description['content']

        embed.set_author(name=MISSAV["name"], url=url, icon_url=MISSAV["icon_url"])

        await message.channel.send(embed=embed)
        await message.edit(suppress=True)

    async def handler_jable(self, message, url, match):
        response = await self.bot.jable_crawl.request(url)
        soup = BeautifulSoup(response, 'html.parser')
        title = soup.find('meta', attrs={'property': 'og:title'})
        image = soup.find('meta', attrs={'property': 'og:image'})

        embed = discord.Embed(title=title['content'], url=url, color=JABLE["color"])
        if image:
            embed.set_image(url=image['content'])

        embed.set_author(name=JABLE["name"], url=url, icon_url=JABLE["icon_url"])

        await message.channel.send(embed=embed)
        await message.edit(suppress=True)

    async def handler_supjav(self, message, url, match):
        embed = await supjav_crawl(url)
        if embed:
            await message.channel.send(embed=embed)
            await message.edit(suppress=True)

    async def handler_baha(self, message, url, match):
        # await message.channel.send(url)
        if message.guild is not None and is_embed_ban(server_id=message.guild.id, arg="baha"):
            return
        bsn = match.group(1)
        if bsn != "60076":
            return
        BAHAENUR = sac_bh.get('BAHAENUR')
        BAHARUNE = sac_bh.get('BAHARUNE')
        embed = await asyncio.to_thread(bahaog, url=url, BAHAENUR=BAHAENUR, BAHARUNE=BAHARUNE, sac_bh=sac_bh)
        print(embed)
        await message.channel.send(embed=embed)
        await message.edit(suppress=True)

    async def handler_facebook(self, message, url, match):
        if message.guild is not None and is_embed_ban(server_id=message.guild.id, arg="fb"):
            return
        try:
            data = await asyncio.wait_for(get_facebook_data(url), timeout=60)
        except Exception as e:
            print(f"[facebook] {url} failed: {e!r}", flush=True)
            return
        print(f"[facebook] {url} -> title={data.get('title')!r} video={bool(data.get('video'))} text={bool(data.get('post_text'))} final={data.get('url')}", flush=True)
        if data and any(data.get(k) for k in ("title", "post_text", "video", "image", "images")):
            post_text = (data.get("post_text") or "")[:4000]
            embed = discord.Embed(title=(data.get("title") or "")[:256] or None, url=url, description=post_text)
            if data.get("views"):
                embed.add_field(name="觀看次數", value=data["views"], inline=True)
            images = data.get("images", [])
            if not images and data.get("image") and not data.get("video"):
                images = [data["image"]]
            if data.get("icon"):
                embed.set_author(name="Facebook", url="https://www.facebook.com/", icon_url=data["icon"])
            else:
                embed.set_author(name="Facebook", url="https://www.facebook.com/", icon_url="https://upload.wikimedia.org/wikipedia/commons/6/6c/Facebook_Logo_2023.png")
            embed.color = discord.Color(0x1877F2)  # Facebook 藍色
            likes = f"👍 {data['likes']}" if data.get("likes") else None
            comments = f"💬 {data['comments']}" if data.get("comments") else None
            shares = f"🔁 {data['shares']}" if data.get("shares") else None
            embed.set_footer(text= "． ".join(filter(None, [likes, comments, shares])))
            if images:
                # 同 URL 的 embed 組成相簿，只顯示貼文前四張附圖。
                embeds = []
                for index, image in enumerate(images[:4]):
                    item = embed if index == 0 else discord.Embed(
                        url=url, color=discord.Color(0x1877F2)
                    )
                    item.set_image(url=image)
                    embeds.append(item)
                await message.channel.send(embeds=embeds)
            else:
                await message.channel.send(embed=embed)
            if data.get("video"):
                await message.channel.send(f"[連結]({data['video']})")
            await message.edit(suppress=True)

    async def handler_kemono(self, message, url, match):
        await self._send_kemono_post(message, url, *match.groups())

    async def handler_kemono_short(self, message, url, match):
        # 沒有創作者 ID 的短網址：API 會告訴我們是哪個創作者
        if not self.is_nsfw_channel(message.channel):
            return
        site, service, post_id = match.groups()
        user_id = await resolve_short_post(self.bot.session, site, service, post_id)
        if user_id:
            await self._send_kemono_post(message, url, site, service, user_id, post_id)

    async def _send_kemono_post(self, message, url, site, service, user_id, post_id):
        if not self.is_nsfw_channel(message.channel):
            return
        if message.guild is not None and is_embed_ban(server_id=message.guild.id, arg="kemono"):
            return
        try:
            embed, pages = await kemono_post_embed(self.bot.session, site, service, user_id, post_id,
                                                   cdn=getattr(self.bot, 'image_cdn', None))
        except Exception as e:
            print(f"[kemono] {url} failed: {e!r}")
            return
        if embed:
            view = KemonoView(session=self.bot.session, embed=embed) if pages > 1 else None
            await message.channel.send(embed=embed, **({"view": view} if view else {}), **cdn_files(embed))
            try:
                await message.edit(suppress=True)
            except discord.Forbidden:
                pass

    async def handler_kemono_creator(self, message, url, match):
        if not self.is_nsfw_channel(message.channel):
            return
        if message.guild is not None and is_embed_ban(server_id=message.guild.id, arg="kemono"):
            return
        try:
            embed = await kemono_creator_embed(self.bot.session, *match.groups())
        except Exception as e:
            print(f"[kemono] {url} failed: {e!r}")
            return
        if embed:
            await message.channel.send(embed=embed)
            try:
                await message.edit(suppress=True)
            except discord.Forbidden:
                pass

    async def _send_video_preview(self, message, site, video_id, name) -> bool:
        """有設定 host.py 的影片預覽頁時，貼預覽頁網址讓 Discord 產生能直接播的影片 embed。
        先問 host 解析結果（host 會快取，Discord 接著來抓預覽頁時立刻有回應）：
        - 檔案不超過上限：貼預覽頁網址（資訊＋影片在同一張卡片，影片網址每次重新解析，不會過期）
        - 全部畫質都太大（Discord 不會產生播放器）：一樣貼預覽頁，host 會改成只有縮圖＋資訊的卡片
        - 影片還沒進 Cloudflare 快取：先貼只有縮圖的卡片，背景預熱，好了再把訊息改成有影片的卡片
        抓不到（沒設定、host 掛了、影片不存在）回傳 False，呼叫端改送一般 embed。"""
        if not config.VIDEO_PREVIEW_BASE:
            return False
        info = await fetch_video_info(self.bot.session, site, video_id)
        if info is None:
            return False
        if not info["playable"]:
            # 超過大小上限只有縮圖卡片，附一個到原站看影片的按鈕（純連結按鈕，不必註冊、重開後也能用）
            view = discord.ui.View()
            view.add_item(discord.ui.Button(label=f"到 {name} 觀看", style=discord.ButtonStyle.link, url=info["page"]))
            await self._send_and_suppress(message, content=f"[▶ {name}]({preview_url(site, video_id)})", view=view)
            return True
        if info.get("cached"):
            await self._send_and_suppress(message, content=f"[▶ {name}]({preview_url(site, video_id)})")
            return True
        sent = await self._send_and_suppress(message, content=f"[▶ {name}]({preview_url(site, video_id, thumb=True)})")
        task = asyncio.create_task(self._warm_then_show_video(sent, site, video_id, name))
        self._warm_tasks.add(task)  # 留住參照，避免背景工作被回收
        task.add_done_callback(self._warm_tasks.discard)
        return True

    async def _warm_then_show_video(self, sent, site, video_id, name):
        if not await warm_video(self.bot.session, site, video_id):
            print(f"[video] {site}/{video_id} 預熱失敗，維持縮圖卡片")
            return
        try:
            await sent.edit(content=f"[▶ {name}]({preview_url(site, video_id, warmed=True)})")
        except discord.HTTPException as e:  # 訊息被刪掉之類的
            print(f"[video] {site}/{video_id} 換成影片卡片失敗: {e!r}")

    async def _send_and_suppress(self, message, **kwargs):
        sent = await message.channel.send(**kwargs)
        try:
            await message.edit(suppress=True)
        except discord.Forbidden:
            pass
        return sent

    async def handler_hitomi(self, message, url, match):
        if not self.is_nsfw_channel(message.channel):
            return
        if message.guild is not None and is_embed_ban(server_id=message.guild.id, arg="hitomi"):
            return
        gallery_id, page = match.groups()
        try:
            embed, pages = await hitomi_embed(self.bot.session, gallery_id, int(page or 1),
                                              cdn=getattr(self.bot, 'image_cdn', None))
        except Exception as e:
            print(f"[hitomi] {url} failed: {e!r}")
            return
        if embed:
            view = HitomiView(session=self.bot.session, embed=embed) if pages > 1 else None
            await self._send_and_suppress(message, embed=embed, **({"view": view} if view else {}), **cdn_files(embed))

    async def handler_ehentai(self, message, url, match):
        site, gid, token = match.groups()
        await self._send_ehentai(message, url, gid, token, 1, ex=site == "ex")

    async def handler_ehentai_page(self, message, url, match):
        # 單頁連結 /s/<imgkey>/<gid>-<頁>：用 API 反查本子 token，從那一頁開始
        if not self.is_nsfw_channel(message.channel):
            return
        site, imgkey, gid, page = match.groups()
        token =await resolve_page_link(self.bot.session, imgkey, gid, page)
        if token:
            await self._send_ehentai(message, url, gid, token, int(page), ex=site == "ex")

    async def _send_ehentai(self, message, url, gid, token, page, ex):
        if not self.is_nsfw_channel(message.channel):
            return
        if message.guild is not None and is_embed_ban(server_id=message.guild.id, arg="ehentai"):
            return
        try:
            embed, pages = await ehentai_embed(self.bot.session, gid, token, page,
                                               cdn=getattr(self.bot, 'image_cdn', None), ex=ex)
        except Exception as e:
            print(f"[ehentai] {url} failed: {e!r}")
            return
        if embed:
            view = EHentaiView(session=self.bot.session, embed=embed) if pages > 1 else None
            await self._send_and_suppress(message, embed=embed, **({"view": view} if view else {}), **cdn_files(embed))

    async def handler_mobile01(self, message, url, match):
        if message.guild is not None and is_embed_ban(server_id=message.guild.id, arg="m01"):
            return
        try:
            # 比對到的網址不含 www，補上才是正式網址
            embeds = await mobile01_embeds(self.bot.mobile01_crawl, url.replace("https://mobile01.com", "https://www.mobile01.com"))
        except Exception as e:
            print(f"[mobile01] {url} failed: {e!r}")
            return
        if embeds:
            await self._send_and_suppress(message, embeds=embeds)

    async def handler_hanime1(self, message, url, match):
        if not self.is_nsfw_channel(message.channel):
            return
        if message.guild is not None and is_embed_ban(server_id=message.guild.id, arg="hanime"):
            return
        if await self._send_video_preview(message, "hanime", match.group(1), "Hanime1"):
            return
        try:
            embed = await hanime1_embed(self.bot.hanime_crawl, match.group(1))
        except Exception as e:
            print(f"[hanime1] {url} failed: {e!r}")
            return
        if embed:
            await self._send_and_suppress(message, embed=embed)

    async def handler_iwara(self, message, url, match):
        if not self.is_nsfw_channel(message.channel):
            return
        if message.guild is not None and is_embed_ban(server_id=message.guild.id, arg="iwara"):
            return
        if await self._send_video_preview(message, "iwara", match.group(1), "Iwara"):
            return
        try:
            embed = await iwara_embed(self.bot.iwara_crawl, match.group(1))
        except Exception as e:
            print(f"[iwara] {url} failed: {e!r}")
            return
        if embed:
            await self._send_and_suppress(message, embed=embed)

    async def handler_iwara_image(self, message, url, match):
        if not self.is_nsfw_channel(message.channel):
            return
        if message.guild is not None and is_embed_ban(server_id=message.guild.id, arg="iwara"):
            return
        try:
            embeds = await iwara_image_embed(self.bot.iwara_crawl, match.group(1))
        except Exception as e:
            print(f"[iwara] {url} failed: {e!r}")
            return
        if embeds:
            await self._send_and_suppress(message, embeds=embeds)

    async def keyword_handler_gacha(self, message):
        data, status = process_gacha_data(message.author.id, message.channel.id)
            
        if status == "lock": return
        if not data: return
            
            # 發送訊息
        await message.channel.send("<:B_env:1076108979375185930>\n<:Arona:1076109041136316496>")
        await message.channel.send("<:result:1076111748106571830>")
        await message.channel.send(data["feed"])
        await message.channel.send(data["stone"])
            
            # 特殊條件跳轉影片/圖
        res_list = data["result"]
        if 4 in res_list:
            await message.channel.send("https://cdn.discordapp.com/attachments/1149330986279108689/1171035321736110100/6bd4b9604ac8b986.mp4")
        if res_list.count(1) == 9 and res_list.count(2) == 1:
            await message.channel.send("https://cdn.discordapp.com/attachments/1040328234463666236/1080134411468689558/IMG_1177.jpg")


async def setup(bot):
    await bot.add_cog(Events(bot))