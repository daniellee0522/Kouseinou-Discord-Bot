# 機器人的應用程式表情：存在 Discord 上，任何伺服器、私訊都能用（伺服器表情要機器人在那個伺服器才顯示得出來）。
# 書籤的網站圖示、抽卡圖示、PU 角色頭像都放這裡；整個 bot 共用一份清單（bot.app_emojis）。
import asyncio
import io
import re

EMOJI_TAG = re.compile(r"<(a?):(\w+):(\d+)>")
EMOJI_SIZE = 128
# imgur 之類的圖床會擋 aiohttp 預設的 User-Agent
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"}


def _emoji_image(data):
    """表情圖片上限 256KB：一律縮到 128x128 以內的 PNG（來源可能是 ico、webp 或很大的圖）"""
    from PIL import Image
    image = Image.open(io.BytesIO(data)).convert("RGBA")
    image.thumbnail((EMOJI_SIZE, EMOJI_SIZE))
    out = io.BytesIO()
    image.save(out, "PNG")
    return out.getvalue()


class AppEmojis:
    def __init__(self, bot):
        self.bot = bot
        self._emojis = None  # 名稱 -> Emoji；None = 還沒讀
        self._load_lock = asyncio.Lock()
        self._pending = {}   # 名稱 -> 建立中的 Task

    @property
    def available(self):
        # discord.py 2.5 以上才有應用程式表情
        return hasattr(self.bot, "create_application_emoji")

    async def load(self):
        if self._emojis is None:
            async with self._load_lock:
                if self._emojis is None:
                    self._emojis = {e.name: e for e in await self.bot.fetch_application_emojis()}
        return self._emojis

    def get(self, name):
        """已經有的表情（'<:名稱:ID>'）；還沒讀清單或沒有這個表情回傳 None，不打 API"""
        emoji = (self._emojis or {}).get(name)
        return str(emoji) if emoji is not None else None

    async def ensure(self, name, image_url):
        """確保有這個表情，沒有就從 image_url 下載建立。回傳 '<:名稱:ID>'，失敗回傳 None。"""
        if not self.available:
            return None
        try:
            emojis = await self.load()
        except Exception as e:
            print(f"[emoji] 讀取應用程式表情失敗: {e!r}", flush=True)
            return None
        if name in emojis:
            return str(emojis[name])
        task = self._pending.get(name)
        if task is None:
            task = self._pending[name] = asyncio.ensure_future(self._create(name, image_url))
            task.add_done_callback(lambda _: self._pending.pop(name, None))
        return await asyncio.shield(task)

    async def _create(self, name, image_url):
        try:
            async with self.bot.session.get(image_url, headers=HEADERS) as resp:
                resp.raise_for_status()
                image = await asyncio.to_thread(_emoji_image, await resp.read())
            emoji = self._emojis[name] = await self.bot.create_application_emoji(name=name, image=image)
            print(f"[emoji] 建立表情 {name}", flush=True)
            return str(emoji)
        except Exception as e:
            print(f"[emoji] 建立表情 {name} 失敗: {e!r}", flush=True)
            return None

    def fix(self, text):
        """把文字裡的 <:名稱:舊ID> 換成同名的應用程式表情；沒有同名的就保留原樣"""
        def replace(match):
            return self.get(match.group(2)) or match.group(0)
        return EMOJI_TAG.sub(replace, text)


def app_emojis(bot) -> AppEmojis:
    store = getattr(bot, "app_emojis", None)
    if store is None:
        store = bot.app_emojis = AppEmojis(bot)
    return store


def cdn_emoji_url(emoji_id):
    """伺服器表情的原圖（就算機器人不在那個伺服器也抓得到）"""
    return f"https://cdn.discordapp.com/emojis/{emoji_id}.png?size=128&quality=lossless"
