# 蔚藍檔案抽卡：圖示與國際服 PU 卡池同步。
# 抽卡用到的圖示原本是某個伺服器的表情，機器人不在那個伺服器就顯示不出來；
# 改成機器人的應用程式表情（同名），圖從 Discord CDN 的原圖建立。
# PU 卡池跟 SchaleDB 記錄的國際服（Global）目前卡池同步，角色頭像建成 ba_<學生 ID> 表情。
# 抽到 PU 時貼該角色的紀念大廳：Kivo（更新最快）→ Blue Archive Wiki → 都沒有就用 SchaleDB 的立繪。
# 紀念大廳的動畫只有 Spine 原始檔（要另外算圖才能變影片），所以只用靜態圖。
import json
import re
import time

import aiohttp

import config
from functions.app_emoji import app_emojis, cdn_emoji_url, EMOJI_TAG

# 抽卡訊息用到的圖示：名稱 -> 原本伺服器表情的 ID
GACHA_EMOJIS = {
    "B_env": 1076108979375185930,
    "Arona": 1076109041136316496,
    "result": 1076111748106571830,
    "SSR": 1075797446598336603,
    "SR": 1075797417787662398,
    "R_": 1075797383184646265,
    "moji": 1075798877573230623,
}
SCHALEDB_CONFIG = "https://schaledb.com/data/config.min.json"
STUDENT_ICON = "https://schaledb.com/images/student/icon/{id}.webp"
STUDENT_PORTRAIT = "https://schaledb.com/images/student/portrait/{id}.webp"
STUDENTS = "https://schaledb.com/data/{lang}/students.min.json"
WIKI_API = "https://bluearchive.wiki/w/api.php"
KIVO_STUDENTS = "https://api.kivo.wiki/api/v1/data/students/"
# 紀念大廳原圖是 4K（約 5MB），請 Wiki 給縮圖，Discord 載入快
LOBBY_WIDTH = 1280
STUDENTS_TTL = 86400
SYNC_REGION = "Global"
PU_FILE = config.DATA_DIR / 'pu.json'


async def warm_student_names(session):
    """啟動時先讀學生名單（約 1.7MB），第一次抽到 PU 時不用等下載"""
    for lang in ("tw", "jp"):
        try:
            await _student_names(session, lang)
        except Exception as e:
            print(f"[ba] 預先讀學生名單（{lang}）失敗: {e!r}", flush=True)


async def ensure_gacha_emojis(bot):
    """抽卡圖示與 pu.json 裡現有角色的表情都建成應用程式表情（已經有的跳過）"""
    store = app_emojis(bot)
    if not store.available:
        return
    for name, emoji_id in GACHA_EMOJIS.items():
        await store.ensure(name, cdn_emoji_url(emoji_id))
    try:
        with open(PU_FILE, 'r', encoding='utf8') as f:
            pool = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return
    for key in pool:
        match = EMOJI_TAG.fullmatch(key)
        if match:
            await store.ensure(match.group(2), cdn_emoji_url(match.group(3)))


async def current_banner(session, region=SYNC_REGION):
    """SchaleDB 記錄的該伺服器目前 PU 學生 ID 清單（可能同時有好幾個卡池，合併）；沒有進行中的卡池回傳 []"""
    async with session.get(SCHALEDB_CONFIG, timeout=aiohttp.ClientTimeout(total=20)) as resp:
        resp.raise_for_status()
        data = await resp.json(content_type=None)
    now = time.time()
    ids = []
    for entry in next((r for r in data.get("Regions", []) if r.get("Name") == region), {}).get("CurrentGacha") or []:
        if entry.get("start", 0) <= now < entry.get("end", 0):
            ids += [i for i in entry.get("characters") or [] if i not in ids]
    return ids


async def sync_pu(bot):
    """pu.json 換成國際服目前的 PU 角色。卡池沒變就不動（保留 /換池 輪到的角色），回傳是否有更新。"""
    store = app_emojis(bot)
    if not store.available:
        return False
    ids = await current_banner(bot.session)
    if not ids:
        return False  # 兩期卡池中間的空檔：維持現狀
    emojis = [await store.ensure(f"ba_{student_id}", STUDENT_ICON.format(id=student_id)) for student_id in ids]
    if None in emojis:
        return False  # 有頭像建不起來，下次再試，不寫入顯示不出來的表情
    async with bot.data_lock:
        try:
            with open(PU_FILE, 'r', encoding='utf8') as f:
                pool = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pool = {}
        if set(pool) == set(emojis):
            return False
        pool = {emoji: index == 0 for index, emoji in enumerate(emojis)}
        with open(PU_FILE, 'w', encoding='utf8') as f:
            json.dump(pool, f, ensure_ascii=False, indent=4)
    print(f"[ba] PU 卡池已同步國際服：{ids}", flush=True)
    return True


_students = {}  # 語言 -> (到期時間, {學生 ID: 名字})
_lobbies = {}   # 學生 ID -> 紀念大廳圖片網址


async def _student_names(session, lang):
    cached = _students.get(lang)
    if cached and cached[0] > time.monotonic():
        return cached[1]
    async with session.get(STUDENTS.format(lang=lang), timeout=aiohttp.ClientTimeout(total=30)) as resp:
        resp.raise_for_status()
        data = await resp.json(content_type=None)
    names = {s["Id"]: s["Name"] for s in (data.values() if isinstance(data, dict) else data)}
    _students[lang] = (time.monotonic() + STUDENTS_TTL, names)
    return names


async def _wiki_lobby(session, english_name):
    """Wiki 的檔名是「Memorial Lobby <英文名>」，副檔名有 png 也有 jpg，兩個一起查"""
    titles = "|".join(f"File:Memorial Lobby {english_name}.{ext}" for ext in ("png", "jpg"))
    params = {"action": "query", "titles": titles, "prop": "imageinfo", "iiprop": "url",
              "iiurlwidth": str(LOBBY_WIDTH), "format": "json"}
    async with session.get(WIKI_API, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
        resp.raise_for_status()
        data = await resp.json(content_type=None)
    for page in data.get("query", {}).get("pages", {}).values():
        info = (page.get("imageinfo") or [{}])[0]
        if info.get("thumburl") or info.get("url"):
            return info.get("thumburl") or info["url"]
    return None


async def _kivo_lobby(session, japanese_name):
    """Kivo 用日文名＋服裝對應（兩邊都用官方日文名；Kivo 的資料偶爾前後有空白）"""
    match = re.fullmatch(r"(.+?)(?:[（(](.+)[）)])?", japanese_name.strip())
    given, skin = match.group(1).strip(), (match.group(2) or "").strip()
    timeout = aiohttp.ClientTimeout(total=15)
    async with session.get(KIVO_STUDENTS, params={"page": "1", "page_size": "20", "name": given}, timeout=timeout) as resp:
        resp.raise_for_status()
        students = (await resp.json(content_type=None)).get("data", {}).get("students") or []
    for student in students:
        if (student.get("given_name_jp") or "").strip() == given and (student.get("skin_jp") or "").strip() == skin:
            async with session.get(f"{KIVO_STUDENTS}{student['id']}", timeout=timeout) as resp:
                resp.raise_for_status()
                image = ((await resp.json(content_type=None)).get("data") or {}).get("recollection_lobby_image")
            if image:
                return "https:" + image if image.startswith("//") else image
    return None


def pu_student_id(pu):
    """pu.json 的 key（<:ba_10145:ID>）裡的學生 ID；舊格式的表情回傳 None"""
    match = re.fullmatch(r"<a?:ba_(\d+):\d+>", pu or "")
    return int(match.group(1)) if match else None


async def pu_showcase(session, student_id):
    """抽到 PU 時要貼的 (角色名, 圖片網址)：紀念大廳，Wiki 沒有就用立繪"""
    names = await _student_names(session, "tw")
    url = _lobbies.get(student_id)
    if url is None:
        for lang, lookup in (("jp", _kivo_lobby), ("en", _wiki_lobby)):
            try:
                name = (await _student_names(session, lang)).get(student_id)
                url = name and await lookup(session, name)
            except Exception as e:
                print(f"[ba] 查紀念大廳 {student_id}（{lookup.__name__}）失敗: {e!r}", flush=True)
                url = None
            if url:
                break
        if url:
            _lobbies[student_id] = url  # Wiki 之後才補上圖的角色，沒找到就不快取，下次再查
    return names.get(student_id, str(student_id)), url or STUDENT_PORTRAIT.format(id=student_id)


async def pu_names(session, keys):
    """pu.json 每個角色的顯示名稱：ba_<學生 ID> 用 SchaleDB 的繁中名，舊格式用表情名稱"""
    names, tw = {}, None
    for key in keys:
        student_id = pu_student_id(key)
        if student_id is not None:
            if tw is None:
                try:
                    tw = await _student_names(session, "tw")
                except Exception as e:
                    print(f"[ba] 讀學生名單失敗: {e!r}", flush=True)
                    tw = {}
            names[key] = tw.get(student_id, f"學生 {student_id}")
        else:
            match = EMOJI_TAG.fullmatch(key)
            names[key] = match.group(2) if match else key
    return names


# 紀念大廳圖片本身：Discord 的圖片代理有時抓不到這些站（尤其 Kivo），由 bot 自己下載、附在訊息上。
# 每張約 0.1～1MB，只留最近幾位學生的
_images = {}   # 學生 ID -> (bytes, 副檔名)
IMAGE_CACHE_SIZE = 8
IMAGE_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"}


async def pu_showcase_image(session, student_id, url):
    """下載紀念大廳圖片，回傳 (bytes, 副檔名)；失敗丟例外"""
    cached = _images.get(student_id)
    if cached:
        return cached
    async with session.get(url, headers=IMAGE_HEADERS, timeout=aiohttp.ClientTimeout(total=15)) as resp:
        resp.raise_for_status()
        data = await resp.read()
        kind = resp.headers.get("Content-Type", "")
    ext = ".png" if "png" in kind else ".webp" if "webp" in kind else ".jpg"
    if len(_images) >= IMAGE_CACHE_SIZE:
        _images.pop(next(iter(_images)))
    _images[student_id] = (data, ext)
    return data, ext
