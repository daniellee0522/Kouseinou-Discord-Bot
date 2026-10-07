import re
import json
import logging
import asyncio
from urllib.parse import urlparse, parse_qs, unquote
from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession
import config

# --------------------------------------------------
# 常數設定
# --------------------------------------------------

HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "accept-language": "en-US,en;q=0.9",
    "cache-control": "no-cache",
    "pragma": "no-cache",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "none",
    "sec-fetch-dest": "document",
    "upgrade-insecure-requests": "1",
}


def load_cookies(path: str = config.DATA_DIR / "fbcookies.json") -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        return {c["name"]: c["value"] for c in raw}
    except (OSError, ValueError, TypeError, KeyError):
        logging.getLogger(__name__).warning("Facebook cookies unavailable; using anonymous access")
        return {}


# --------------------------------------------------
# 字串 / 數字工具
# --------------------------------------------------

def clean_title(title: str):
    if not title:
        return title
    # 中文格式：636 萬次觀看 · 10 萬個心情 | 標題
    m = re.match(
        r"^[\d,.\s萬億\xa0]+次觀看\s*·\s*[\d,.\s萬億\xa0]+個心情\s*\|\s*(.+)$",
        title, re.DOTALL,
    )
    if m:
        return m.group(1).strip()
    # 英文格式：6.3M views · 102K reactions | 標題
    m = re.match(
        r"^[\d,.]+[KMB]?\s+views\s*·\s*[\d,.]+[KMB]?\s+reactions\s*\|\s*(.+)$",
        title, re.DOTALL,
    )
    if m:
        return m.group(1).strip()
    return title


def extract_views_likes_from_title(title: str):
    if not title:
        return None, None
    # 中文格式
    m = re.match(
        r"^([\d,.\s萬億\xa0]+)次觀看\s*·\s*([\d,.\s萬億\xa0]+)個心情",
        title,
    )
    if m:
        return m.group(1), m.group(2)
    # 英文格式：6.3M views · 102K reactions
    m = re.match(
        r"^([\d,.]+[KMB]?)\s+views\s*·\s*([\d,.]+[KMB]?)\s+reactions",
        title,
    )
    if m:
        return m.group(1), m.group(2)
    return None, None


def _parse_english_number(s: str):
    """解析 6.3M / 102K / 3.9B 格式"""
    s = s.replace(",", "").strip()
    m = re.match(r"([\d.]+)([KMB]?)$", s)
    if not m:
        return None
    num = float(m.group(1))
    suffix = m.group(2)
    multipliers = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}
    return int(num * multipliers.get(suffix, 1))


def is_video_or_reels_title(title: str) -> bool:
    if not title:
        return False
    if re.match(r"^[\d,.\s萬億\xa0]+次觀看", title):
        return True
    if re.match(r"^[\d,.]+[KMB]?\s+views", title):
        return True
    return False


def is_reel_url(url: str) -> bool:
    return bool(re.search(r"/(reel|videos)/", url))


def remove_common_parts(s1: str, s2: str) -> str:
    match = re.search(r"\|(.*)$", s1)
    if match and s2 in s1:
        return match.group(1).strip()
    return s1


# --------------------------------------------------
# JSON 區塊工具
# --------------------------------------------------

def get_json_blocks(soup: BeautifulSoup) -> list[dict]:
    script_elements = soup.find_all(
        "script",
        attrs={"type": "application/json", "data-content-len": True, "data-sjs": True},
    )
    script_elements.sort(key=lambda e: int(e.attrs["data-content-len"]), reverse=True)
    blocks = []
    for e in script_elements:
        try:
            blocks.append(json.loads(e.text))
        except Exception:
            pass
    return blocks


def jq_enumerate(obj) -> list:
    result = []

    def collect(value):
        if isinstance(value, dict):
            result.append(value)
            for v in value.values():
                if isinstance(v, (list, dict)):
                    collect(v)
        elif isinstance(value, list):
            for item in value:
                collect(item)

    collect(obj)
    return result


def jq_all(obj, key: str) -> list:
    return [oo[key] for oo in jq_enumerate(obj) if key in oo]


def jq_first(obj, key: str):
    for oo in jq_enumerate(obj):
        if key in oo:
            return oo[key]
    return None


# --------------------------------------------------
# 解析輔助：從 JSON blocks 撈貼文文字與圖片
# --------------------------------------------------

import html as html_lib

def _extract_icon_uri_from_html(html: str):
    """從原始 HTML 用 regex 撈 SVG <image> 裡的 t1.xxx-1 頭貼"""
    m = re.search(r'xlink:href="(https://[^"]+/t1\.[^"]+)"', html)
    if m:
        return html_lib.unescape(m.group(1))
    return None


def _is_viewer(node: dict, viewer_id: str) -> bool:
    """登入 cookie 的帳號（c_user）本人，不可當作發文者"""
    return bool(viewer_id) and str(node.get("id")) == viewer_id


def _extract_author_name(root: dict, owner_id: str = None, viewer_id: str = None):
    """從 JSON blocks 撈發文者名字，按優先順序嘗試多個路徑"""
    # 方法0: 已知擁有者 id（reel 的 actor 是登入者本人，不能用）
    if owner_id:
        for oo in jq_enumerate(root):
            if isinstance(oo, dict):
                for key in ("owner", "actor", "video_owner"):
                    v = oo.get(key)
                    if isinstance(v, dict) and str(v.get("id")) == owner_id \
                            and str(v.get("id")) != viewer_id \
                            and isinstance(v.get("name"), str) and v["name"]:
                        return v["name"]

    # 方法1: actor -> name（最常見，一般貼文、photo）
    for oo in jq_enumerate(root):
        if "actor" in oo and isinstance(oo["actor"], dict) and not _is_viewer(oo["actor"], viewer_id):
            name = oo["actor"].get("name")
            if name and isinstance(name, str):
                return name

    # 方法2: owner -> name（Reel / video 頁常見）
    for oo in jq_enumerate(root):
        if "owner" in oo and isinstance(oo["owner"], dict) and not _is_viewer(oo["owner"], viewer_id):
            name = oo["owner"].get("name")
            if name and isinstance(name, str):
                return name

    # 方法3: creation_story -> actor -> name
    cs = jq_first(root, "creation_story")
    if isinstance(cs, dict):
        actor = cs.get("actor")
        if isinstance(actor, dict) and not _is_viewer(actor, viewer_id):
            name = actor.get("name")
            if name:
                return name

    # 方法4: short_form_video_context -> video_owner -> name
    sfvc = jq_first(root, "short_form_video_context")
    if isinstance(sfvc, dict):
        vo = sfvc.get("video_owner")
        if isinstance(vo, dict) and not _is_viewer(vo, viewer_id):
            name = vo.get("name")
            if name:
                return name

    return None


def _extract_post_text(root: dict) :
    """從 JSON blocks 撈貼文內文（story_message / message）"""
    for key in ("story_message", "message"):
        val = jq_first(root, key)
        if isinstance(val, dict):
            text = jq_first(val, "text")
            if text:
                return text
        elif isinstance(val, str) and val:
            return val
    return None

def _extract_icon_uri(root: dict, soup: BeautifulSoup = None) -> str:
    """優先從 HTML 的 SVG <image> 撈發布者大頭貼（t1.6435-1），fallback 到 JSON"""

    # 方法1: 從 HTML SVG <image xlink:href> 找 t1.6435-1 的頭貼
    if soup:
        for img in soup.find_all("image"):
            href = img.get("xlink:href") or img.get("href") or ""
            if "t1." in href and "-1/" in href:
                return href
    print("Debug: 從 HTML 撈頭貼失敗，開始 fallback JSON...")

    # 方法2: fallback 到原本的 JSON 邏輯
    for oo in jq_enumerate(root):
        uri = oo.get("uri")
        if not uri or not isinstance(uri, str):
            continue
        if not uri.startswith("http"):
            continue
        if "t39.30808-1" not in uri:
            continue
        if not re.search(r"stp=[^&]*s\d+x\d+", uri):
            continue
        return uri
    return None

def _extract_image_by_fbid(root: dict, url: str):
    """優先解法：貼文網址（或轉址後網址）常帶有該相片的 fbid，
    直接在 JSON blocks 裡找 id 完全等於該 fbid 的 Photo 節點，取其 image.uri，
    避免誤抓到留言區、相關貼文等其他圖片"""
    if not url:
        return None
    m = re.search(r"[?&]fbid=(\d+)(?:&|$)", url) or re.search(r"/photos/(?:[^/]+/)*(\d+)(?:/|$)", url)
    if not m:
        return None
    fbid = m.group(1)
    for oo in jq_enumerate(root):
        if str(oo.get("id")) != fbid or oo.get("__typename") != "Photo":
            continue
        image = oo.get("image")
        if isinstance(image, dict) and isinstance(image.get("uri"), str):
            return image["uri"]
    return None


def _post_id_from_url(url: str):
    parsed = urlparse(url or "")
    query = parse_qs(parsed.query)
    if query.get("story_fbid"):
        return query["story_fbid"][0]
    match = re.search(r"/(?:posts|permalink)/([^/]+)(?:/([^/]+))?", unquote(parsed.path))
    if match:
        return match.group(2) or match.group(1)
    return None


def _post_nodes(obj):
    """搜尋貼文時跳過留言、回饋與附帶／推薦內容。"""
    if isinstance(obj, dict):
        if "Comment" in str(obj.get("__typename", "")):
            return
        yield obj
        for key, value in obj.items():
            if any(word in key.lower() for word in ("comment", "feedback", "recommend")):
                continue
            if key in ("attached_story", "attachments", "actors", "author"):
                continue
            yield from _post_nodes(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _post_nodes(value)


def _extract_image_uris(root: dict, *urls: str):
    """只接受網址指向的貼文附件，不以 CDN 格式推測圖片歸屬。"""
    target_ids = {pid for url in urls if (pid := _post_id_from_url(url))}
    if not target_ids:
        return []
    nodes = list(_post_nodes(root))
    matches = [node for node in nodes if (
        str(node.get("post_id")) in target_ids
        or _post_id_from_url(node.get("permalink_url") or node.get("wwwURL") or "") in target_ids
    )]
    # 同一貼文的附件可能分散在不同的 Relay fragment。
    story_ids = {node["id"] for node in matches if node.get("id")}
    matches.extend(node for node in nodes if node.get("id") in story_ids)
    images = []
    seen = set()
    for story in matches:
        for node in _post_nodes(story.get("attachments", [])):
            media = node.get("media")
            if not isinstance(media, dict) or media.get("__typename") != "Photo":
                continue
            for key in ("image", "photo_image", "large_image"):
                image = media.get(key)
                uri = image.get("uri") if isinstance(image, dict) else None
                if isinstance(uri, str) and uri.startswith("https://"):
                    identity = str(media.get("id") or urlparse(uri).path)
                    if identity not in seen:
                        seen.add(identity)
                        images.append(uri)
                    break
    return images


def _extract_image_uri(root: dict, *urls: str):
    images = _extract_image_uris(root, *urls)
    return images[0] if images else None


def _merge_images(*groups):
    images = []
    seen = set()
    for group in groups:
        for uri in group:
            # CDN host / 簽名可能因登入狀態不同，同一路徑仍是同張圖。
            identity = urlparse(uri).path
            if identity not in seen:
                seen.add(identity)
                images.append(uri)
    return images


def _target_video_ids(url: str) -> set:
    """從網址取出該貼文自己的影片 / 貼文 id（reel、videos、watch?v=、story_fbid、fbid）"""
    ids = set(re.findall(r'/(?:reel|videos)/(?:[^/?]+/)?(\d+)', url))
    ids |= set(re.findall(r'[?&](?:v|story_fbid|fbid|video_id)=(\d+)', url))
    return ids


def _extract_video_url(html: str, final_url: str = ""):
    """只撈「屬於這則貼文」的影片網址（HD 優先，SD 備用）。
    頁面常夾帶推薦 / 其他貼文的影片，所以必須以網址中的 id 比對，比不到就不回傳"""
    targets = _target_video_ids(final_url)
    if not targets:
        return None
    groups = [m.start() for m in re.finditer(r'"progressive_urls"', html)]
    for i, start in enumerate(groups):
        ids = re.findall(r'dash_mpd_debug\.mpd\?v=(\d+)', html[max(0, start - 6000):start])
        if not ids or ids[-1] not in targets:
            continue
        end = groups[i + 1] if i + 1 < len(groups) else start + 20000
        found = {}
        for m in re.finditer(r'"progressive_url"\s*:\s*"((?:[^"\\]|\\.)*)"[^{}]*?"metadata"\s*:\s*\{[^{}]*?"quality"\s*:\s*"(\w+)"', html[start:end]):
            try:
                found.setdefault(m.group(2), json.loads(f'"{m.group(1)}"'))
            except ValueError:
                continue
        url = found.get("HD") or found.get("SD") or next(iter(found.values()), None)
        if url:
            return url
    return None


def _extract_reel_text(html: str, final_url: str):
    """reel 頁面含多支影片的 message，取離該影片 id 最近的那一則"""
    m = re.search(r'/reel/(\d+)', final_url)
    if not m:
        return None
    positions = [x.start() for x in re.finditer(m.group(1), html)]
    best = None
    for msg in re.finditer(r'"message"\s*:\s*\{\s*"text"\s*:\s*"((?:[^"\\]|\\.)*)"', html):
        if not positions:
            break
        dist = min(abs(msg.start() - p) for p in positions)
        if dist < 8000 and (best is None or dist < best[0]):
            try:
                text = json.loads(f'"{msg.group(1)}"')
            except ValueError:
                continue
            if text.strip():
                best = (dist, text)
    return best[1] if best else None


def _extract_counts_from_html(html: str):
    """從原始 HTML regex 補撈 comments / shares"""
    comments = shares = None
    m = re.search(r'"total_comment_count"\s*:\s*(\d+)', html)
    if m:
        comments = int(m.group(1))
    m = re.search(r'"share_count_reduced"\s*:\s*"([^"]+)"', html)
    if m:
        shares = m.group(1)
    return comments, shares


# --------------------------------------------------
# 解析函式（純 CPU，不需要 async）
# --------------------------------------------------

def parse_anonymous(html: str, final_url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    # OG meta
    og = {tag["property"]: tag.get("content") for tag in soup.select("meta[property^='og:']")}
    raw_title = og.get("og:title", "")
    views = likes = None

    if is_video_or_reels_title(raw_title):
        views, likes = extract_views_likes_from_title(raw_title)

    # 互動數：從 JSON blocks 撈
    blocks = get_json_blocks(soup)
    root = {"blocks": blocks}
    post_counts = {"likes": None, "comments": None, "shares": None, "icon": None}  # ★ 新增 icon 欄位

    for bloc in blocks:
        renderer = jq_first(bloc, "comet_ufi_summary_and_actions_renderer")
        if not renderer:
            continue
        try:
            fb = renderer["feedback"]
            post_counts["likes"]    = fb["i18n_reaction_count"]
            post_counts["comments"] = fb["comment_rendering_instance"]["comments"]["total_count"]
            post_counts["shares"]   = fb["i18n_share_count"]
            break
        except (KeyError, TypeError):
            continue

    # regex 補撈
    html_comments, html_shares = _extract_counts_from_html(html)
    if post_counts["comments"] is None:
        post_counts["comments"] = html_comments
    if post_counts["shares"] is None:
        post_counts["shares"] = html_shares
    if not post_counts["icon"]:                          # ★ 新增
            post_counts["icon"] = _extract_icon_uri_from_html(html) or  _extract_icon_uri(root)   # ★ 新增

    # 圖片 / 影片
    images = _extract_image_uris(root, final_url, og.get("og:url") or "")
    photo = _extract_image_by_fbid(root, final_url)
    if photo and not images:
        images = [photo]
    image = images[0] if images else None
    if not image and is_reel_url(final_url):
        image = og.get("og:image")
    video = _extract_video_url(html, final_url)

    # title：固定取 og:title（發文者名字）
    # post_text：固定獨立撈內文，不互相 fallback
    title = clean_title(raw_title) if raw_title else None
    post_text = _extract_post_text(root)

    return {
        "video":       video,
        "image":       image,
        "images":      images,
        "title":       title,
        "post_text":   post_text,
        "description": og.get("og:description"),
        "url":         og.get("og:url") or final_url,
        "views":       views,
        "likes":       likes or post_counts["likes"],
        "comments":    post_counts["comments"],
        "shares":      post_counts["shares"],
        "icon":        post_counts["icon"],
    }


def parse_logged_in(html: str, final_url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    blocks = get_json_blocks(soup)
    root = {"blocks": blocks}

    result = {
        "video": None, "image": None, "images": [], "title": None, "post_text": None, "icon": None,
        "description": None, "url": final_url,
        "views": None, "likes": None, "comments": None, "shares": None,
    }

    if is_reel_url(final_url):
        result["video"] = _extract_video_url(html, final_url)
        result["post_text"] = _extract_reel_text(html, final_url)

        pt = jq_first(root, "preferred_thumbnail")
        if isinstance(pt, dict):
            result["image"] = (pt.get("image") or {}).get("uri")

        sfvc = jq_first(root, "short_form_video_context")
        if isinstance(sfvc, dict):
            result["url"] = sfvc.get("shareable_url") or final_url

        vc = jq_first(root, "video_view_count")
        if isinstance(vc, int):
            result["views"] = vc

        cs = jq_first(root, "creation_story")
        video_id = str(cs["id"]) if cs and "id" in cs else None

        if video_id:
            matched = [
                bloc for bloc in blocks
                if jq_first(bloc, "unified_reactors")
                and video_id in [str(i) for i in jq_all(bloc, "id")]
            ]
            if matched:
                for fb in jq_all(matched[0], "feedback"):
                    if not isinstance(fb, dict):
                        continue
                    if result["likes"] is None:
                        ur = fb.get("unified_reactors")
                        if isinstance(ur, dict):
                            result["likes"] = ur.get("count")
                    if result["comments"] is None:
                        tc = fb.get("total_comment_count")
                        if isinstance(tc, int):
                            result["comments"] = tc
                    if result["shares"] is None:
                        scr = fb.get("share_count_reduced")
                        if scr is not None:
                            result["shares"] = scr

    else:
        # 一般貼文 / photo
        for bloc in blocks:
            renderer = jq_first(bloc, "comet_ufi_summary_and_actions_renderer")
            if not renderer:
                continue
            try:
                fb = renderer["feedback"]
                result["likes"]    = fb["i18n_reaction_count"]
                result["comments"] = fb["comment_rendering_instance"]["comments"]["total_count"]
                result["shares"]   = fb["i18n_share_count"]
                break
            except (KeyError, TypeError):
                continue

        result["video"] = _extract_video_url(html, final_url)

        # photo 頁面 fallback
        result["images"] = _extract_image_uris(root, final_url)
        photo = _extract_image_by_fbid(root, final_url)
        if photo and not result["images"]:
            result["images"] = [photo]
        result["image"] = result["images"][0] if result["images"] else None
        # post_text 永遠獨立撈，不放進 title
        result["post_text"] = _extract_post_text(root)
        if not result["icon"]:                          # ★ 新增
            result["icon"] = _extract_icon_uri(root)

    return result


def merge_results(anon: dict, logged: dict) -> dict:
    images = _merge_images(anon.get("images", []), logged.get("images", []))
    return {
        "video":       anon.get("video") or logged.get("video"),
        "image":       images[0] if images else anon.get("image") or logged.get("image"),
        "images":      images,
        "title":       anon.get("title")       or logged.get("title"),
        "post_text":   anon.get("post_text")   or logged.get("post_text"),
        "description": anon.get("description") or logged.get("description"),
        "url":         anon.get("url")         or logged.get("url"),
        "views":       logged.get("views")     or anon.get("views"),
        "likes":       logged.get("likes")     or anon.get("likes"),
        "comments":    logged.get("comments")  or anon.get("comments"),
        "shares":      logged.get("shares")    or anon.get("shares"),
        "icon":        anon.get("icon")      or logged.get("icon"),
    }


# --------------------------------------------------
# 異步抓取
# --------------------------------------------------

def debug_images(html: str):
    soup = BeautifulSoup(html, "html.parser")
    blocks = get_json_blocks(soup)
    root = {"blocks": blocks}
    for oo in jq_enumerate(root):
        uri = oo.get("uri", "")
        if "t39.30808-6" in uri and ".jpg" in uri:
            print(oo)
            print("---")


async def fetch_html(session: AsyncSession, url: str, cookies: dict = None) -> tuple[str, str]:
    resp = await session.get(url, headers=HEADERS, cookies=cookies or {}, timeout=15)
    return resp.text, str(resp.url)


def _normalize_url(url: str) -> str:
    """facebook.com / m.facebook.com 一律換成 www，否則登入 cookie 抓不到 reel 頁"""
    return re.sub(r'^(https?://)(?:m\.|web\.)?facebook\.com', r'\1www.facebook.com', url)


def _reel_url_from_share(url: str, final_url: str):
    """share/r 被導到 story.php 時，直接用 story_fbid 組出 reel 網址"""
    if "/share/r/" not in url or "story.php" not in final_url:
        return None
    m = re.search(r'story_fbid=(\d+)', final_url)
    return f"https://www.facebook.com/reel/{m.group(1)}/" if m else None


async def get_facebook_data(url: str) -> dict:
    url = _normalize_url(url)
    cookies = load_cookies()
    viewer_id = cookies.get("c_user")
    async with (
        AsyncSession(impersonate="chrome120") as anon_session,
        AsyncSession(impersonate="chrome120") as logged_session,
    ):
        if cookies:
            results = await asyncio.gather(
                fetch_html(anon_session, url, {}),
                fetch_html(logged_session, url, cookies),
                return_exceptions=True,
            )
            if all(isinstance(r, Exception) for r in results):
                raise results[0]
            # 其中一邊失敗（逾時 / 被擋）時，用另一邊的結果繼續
            (html_anon, final_url_anon), (html_logged, final_url_logged) = (
                r if not isinstance(r, Exception) else ("", url) for r in results
            )
        else:
            html_anon, final_url_anon = await fetch_html(anon_session, url, {})
            html_logged, final_url_logged = "", final_url_anon
    reel_url = _reel_url_from_share(url, final_url_logged)
    if reel_url and cookies and "progressive_url" not in html_logged:
        async with AsyncSession(impersonate="chrome120") as retry_session:
            html_logged, final_url_logged = await fetch_html(retry_session, reel_url, cookies)
    # print(debug_images(html_anon))
    anon_result   = parse_anonymous(html_anon,   final_url_anon)
    logged_result = parse_logged_in(html_logged, final_url_logged)
    data = merge_results(anon_result, logged_result)

    # m_anon = re.search(r'xlink:href="(https://[^"]+/t1\.[^"]+)"', html_anon)
    # m_logged = re.search(r'xlink:href="(https://[^"]+/t1\.[^"]+)"', html_logged)
    # print("ANON t1:", m_anon.group(1) if m_anon else None)
    # print("LOGGED t1:", m_logged.group(1) if m_logged else None)

    # 若 description 已包含在 title 裡，只保留 | 後面的部分
    if data["description"] and data["title"] and \
            data["description"] in data["title"] and "|" in data["title"]:
        data["title"] = remove_common_parts(data["title"], data["description"])

    # 偵測 og:title 是否其實是內文而非發文者名字
    # 判斷依據：title 出現在 post_text 開頭（og:title 把內文當標題了）
    if data["post_text"] and data["title"] and data["title"] in data["post_text"]:
        data["title"] = None

    # title 仍為 None → fallback 從 JSON 撈發文者名字
    if not data["title"]:
        oid = re.search(r'[?&]id=(\d+)', final_url_anon) or re.search(r'[?&]id=(\d+)', final_url_logged)
        oid = oid.group(1) if oid else None
        if not oid:
            m = re.search(r'content_owner_id_new\\?"\s*:\s*\\?"(\d+)', html_logged)
            oid = m.group(1) if m else None
        data["title"] = _extract_author_name(
            {"blocks": get_json_blocks(BeautifulSoup(html_anon, "html.parser"))}, oid, viewer_id
        ) or _extract_author_name(
            {"blocks": get_json_blocks(BeautifulSoup(html_logged, "html.parser"))}, oid, viewer_id
        )

    data["icon"] = None

    return data


# --------------------------------------------------
# 測試
# --------------------------------------------------

async def main():
    urls = [
        "https://www.facebook.com/share/1GqrDft94X/?mibextid=wwXIfr",
        "https://www.facebook.com/share/p/18YdPb4Dhy/?mibextid=wwXIfr",
    ]
    for url in urls:
        print(f"\n{'='*60}")
        print(f"URL: {url}")
        data = await get_facebook_data(url)
        for k, v in data.items():
            if k == "video":
                print(f"  video: {'有 ' + v if v else '無'}")
            else:
                print(f"  {k}: {v}")


if __name__ == "__main__":
    asyncio.run(main())
