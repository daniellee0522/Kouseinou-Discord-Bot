# hanime1 / iwara 影片預覽：貼 host.py 的預覽頁，影片太大時 host 會改成只有縮圖＋資訊的卡片。
# 影片還沒進 Cloudflare 快取時，Discord 產生預覽要整支下載、經過我們約 6MB/s 的上傳常常超過它約 8.5 秒的時限，
# 卡片就不顯示；所以先貼只有縮圖的卡片，背景請 host 把影片灌進快取，好了再把訊息改成有影片的卡片。
import aiohttp

import config

# Discord 會依網址快取 embed；預覽頁格式改版時把 v 加一，舊網址的快取才不會蓋掉新格式
PREVIEW_VERSION = 10


def preview_url(site, video_id, thumb=False, warmed=False):
    """thumb：只有縮圖的卡片（預熱中）。warmed：預熱完換上的網址，跟先前可能抓失敗、被 Discord 快取的網址分開"""
    extra = "&thumb=1" if thumb else "&w=1" if warmed else ""
    return f"{config.VIDEO_PREVIEW_BASE}/p/{site}/{video_id}?v={PREVIEW_VERSION}{extra}"


async def _get_json(session, url, timeout):
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
            if resp.status != 200:
                print(f"[video] {url} -> {resp.status}")
                return None
            return await resp.json()
    except Exception as e:
        print(f"[video] {url} failed: {e!r}")
        return None


async def fetch_video_info(session, site, video_id):
    """host.py 的 /api/site_video：影片資訊、能不能經過預覽頁播、是否已在 Cloudflare 快取。失敗回傳 None。"""
    return await _get_json(session, f"{config.VIDEO_PREVIEW_BASE}/api/site_video/{site}/{video_id}", 90)


async def warm_video(session, site, video_id) -> bool:
    """請 host 把整支影片灌進 Cloudflare 快取，回傳是否成功"""
    data = await _get_json(session, f"{config.VIDEO_PREVIEW_BASE}/api/site_video/{site}/{video_id}/warm", 150)
    return bool(data and data.get("cached"))
