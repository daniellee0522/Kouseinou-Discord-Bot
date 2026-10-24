import os
import re
import threading
import functools
import json
import time
import datetime
import pytz
import requests
from bs4 import BeautifulSoup
import config


ANI_URL = 'https://ani.gamer.com.tw/'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Safari/537.36',
}
R18_SUFFIX = "(年齡限制)"
WEEK_LST = ["一", "二", "三", "四", "五", "六", "日"]
# 首頁找不到這部動畫超過這麼久才自動取消訂閱（避免一次解析失敗就把訂閱刪光）
MISSING_LIMIT_SEC = 7 * 24 * 3600
# 播出時間前 FAST_POLL_BEFORE 秒到後 FAST_POLL_AFTER 秒內，還沒抓到新集數就密集輪詢
FAST_POLL_BEFORE = 60
FAST_POLL_AFTER = 30 * 60
TW_TZ = pytz.timezone('Asia/Taipei')

# sub.json 會被 thread 同時讀寫（指令 + 排程），用鎖避免互相覆蓋
_SUB_LOCK = threading.RLock()


def _sub_lock(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        with _SUB_LOCK:
            return func(*args, **kwargs)
    return wrapper


def _sub_path():
    return config.DATA_DIR / 'sub.json'


def _load_subs():
    try:
        with open(_sub_path(), 'r', encoding='utf8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def _save_subs(data):
    # 先寫暫存檔再取代，避免寫到一半被中斷而弄壞 sub.json
    path = _sub_path()
    tmp = path.with_name(path.name + '.tmp')
    with open(tmp, 'w', encoding='utf8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    os.replace(tmp, path)


def episode_number(episode):
    """'第12集' -> 12.0，'第12.5集' -> 12.5，解析不到回傳 None"""
    m = re.search(r'(\d+(?:\.\d+)?)', episode or '')
    return float(m.group(1)) if m else None


def is_newer_episode(new, old):
    new_num, old_num = episode_number(new), episode_number(old)
    if new_num is not None and old_num is not None:
        return new_num > old_num
    return new != old


def _base_name(name):
    if name.endswith(R18_SUFFIX):
        return name[:-len(R18_SUFFIX)]
    return name


def _fetch_homepage():
    try:
        r = requests.get(ANI_URL, headers=HEADERS, timeout=10)
    except requests.RequestException as e:
        print(f'請求失敗：{e}')
        return None
    if r.status_code != 200:
        print(f'請求失敗：{r.status_code}')
        return None
    return r.text


def _text(node):
    return node.text.strip() if node is not None else ''


def parse_timeline(html):
    """解析首頁「本季新番」，每部動畫只保留最新一集。

    return = [{name, base_name, r18, episode, href, image, weekday(1~7), time('HHMM')}]
    """
    soup = BeautifulSoup(html, 'html.parser')
    block = soup.select_one('.timeline-ver > .newanime-block')
    if block is None:
        return []
    result = {}
    for item in block.select('.newanime-date-area:not(.premium-block)'):
        base_name = _text(item.find('p', class_='anime-name'))
        if not base_name:
            continue
        labels = [_text(s) for s in item.select('.anime-label-block span')]
        r18 = "年齡限制" in labels
        weekday = None
        m = re.search(r'\((.)\)', _text(item.select_one('.newanime-date-area>span')))
        if m and m.group(1) in WEEK_LST:
            weekday = WEEK_LST.index(m.group(1)) + 1
        link = item.select_one('a.anime-card-block')
        image = item.select_one('.lazyload')
        entry = {
            "name": base_name + R18_SUFFIX if r18 else base_name,
            "base_name": base_name,
            "r18": r18,
            "episode": _text(item.select_one('.anime-episode')),
            "href": ANI_URL + link.get('href', '') if link is not None else ANI_URL,
            "image": image.get('data-src') if image is not None else None,
            "weekday": weekday,
            "time": _text(item.select_one('.anime-hours-block>span')).replace(":", ""),
        }
        old = result.get(entry["name"])
        if old is None or is_newer_episode(entry["episode"], old["episode"]):
            result[entry["name"]] = entry
    return list(result.values())


def parse_schedule(html):
    """解析首頁「週期表」，這是之後的播出時間，動畫改期時會先反映在這裡。

    return = {動畫名(不含年齡限制): (weekday(1~7), 'HHMM')}
    """
    soup = BeautifulSoup(html, 'html.parser')
    schedule = {}
    for day in soup.select('.programlist-block .day-list'):
        title = _text(day.select_one('.day-title'))
        if not title or title[-1] not in WEEK_LST:
            continue
        weekday = WEEK_LST.index(title[-1]) + 1
        for info in day.select('.text-anime-info'):
            name = _text(info.select_one('.text-anime-name'))
            hhmm = _text(info.select_one('.text-anime-time')).replace(":", "")
            if name and hhmm:
                schedule[name] = (weekday, hhmm)
    return schedule


def _find_entry(entries, input_name, R_18):
    want_r18 = R_18 in ("r", "R") or input_name.endswith(R18_SUFFIX)
    key = _base_name(input_name).lower()
    for entry in entries:
        if key in entry["base_name"].lower():
            if want_r18 and not entry["r18"]:
                continue
            return entry
    return None


#return = [動畫名,動畫集數,播放網址,動畫縮圖]
def anime_get_info(input_name, R_18="n"):
    html = _fetch_homepage()
    if html is None:
        return "fail to connect"
    entry = _find_entry(parse_timeline(html), input_name, R_18)
    if entry is None:
        return []
    return [entry["name"], entry["episode"], entry["href"], entry["image"]]


#return = 動畫名 / "repeated" / "not found" / None(連線失敗)
def anime_get_info_add(input_name, server_id, R_18="n"):
    html = _fetch_homepage()
    if html is None:
        return None
    entries = parse_timeline(html)
    entry = _find_entry(entries, input_name, R_18)
    if entry is None:
        return "not found"
    weekday, hhmm = parse_schedule(html).get(entry["base_name"], (entry["weekday"], entry["time"]))
    with _SUB_LOCK:
        data = _load_subs()
        subs = data.setdefault(str(server_id), [])
        if any(sub["name"].lower() == entry["name"].lower() for sub in subs):
            return "repeated"
        subs.append({
            "name": entry["name"],
            "episode": entry["episode"],
            "update_date": weekday,
            "update_time": hhmm,
        })
        _save_subs(data)
    return entry["name"]


#return = [[動畫名,目前集數,網址,星期幾,幾點]]
def anime_lst():
    html = _fetch_homepage()
    if html is None:
        return "fail to connect"
    search_lst = []
    for entry in parse_timeline(html):
        if entry["weekday"] is None:
            continue
        hhmm = entry["time"]
        search_lst.append([entry["name"], entry["episode"], entry["href"],
                           '星期' + WEEK_LST[entry["weekday"] - 1], hhmm[:2] + ":" + hhmm[2:]])
    return search_lst


@_sub_lock
def subscribed_names(server_id):
    return [sub["name"] for sub in _load_subs().get(str(server_id), [])]


@_sub_lock
def list_subscriptions(server_id):
    subs = list(_load_subs().get(str(server_id), []))
    subs.sort(key=lambda x: (x.get("update_date") or 8, x.get("update_time") or "", x["name"]))
    return subs


#return = 被刪除的動畫名 / "no r18" / None(沒有訂閱)
@_sub_lock
def remove_subscription(server_id, anime_name, R_18="n"):
    data = _load_subs()
    subs = data.get(str(server_id), [])
    key = anime_name.lower()
    matches = [sub for sub in subs if key in sub["name"].lower()]
    if not matches:
        return None
    if R_18 in ("r", "R"):
        targets = [sub for sub in matches if sub["name"].endswith(R18_SUFFIX)]
        if not targets:
            return "no r18"
    else:
        targets = [sub for sub in matches if not sub["name"].endswith(R18_SUFFIX)] or matches
    subs.remove(targets[0])
    if not subs:
        data.pop(str(server_id), None)
    _save_subs(data)
    return targets[0]["name"]


def apply_updates(data, entries, schedule, now=None):
    """依首頁資料更新訂閱，回傳 (是否有變更, 新集數通知, 已結束而移除的動畫)

    通知格式 = (server_id, {name, episode, href, image})
    """
    now = time.time() if now is None else now
    by_name = {entry["name"]: entry for entry in entries}
    by_base = {entry["base_name"]: entry for entry in entries}
    changed = False
    notifications = []
    removed = []
    for server_id in list(data):
        kept = []
        seen = set()
        for sub in data[server_id]:
            # 舊版會重複訂閱同一部，留第一筆就好，否則每集會推播兩次
            if sub["name"].lower() in seen:
                changed = True
                continue
            seen.add(sub["name"].lower())
            # 舊資料的年齡限制標記可能和現在解析的不同，退而用原名比對
            entry = by_name.get(sub["name"]) or by_base.get(_base_name(sub["name"]))
            if entry is None:
                missing_since = sub.setdefault("missing_since", now)
                if missing_since == now:
                    changed = True
                if now - missing_since >= MISSING_LIMIT_SEC:
                    removed.append((server_id, sub["name"]))
                    changed = True
                    continue
                kept.append(sub)
                continue
            if sub.pop("missing_since", None) is not None:
                changed = True
            # 動畫改期：以週期表（之後的播出時間）為準，沒有才用最近一集的播出時間
            weekday, hhmm = schedule.get(entry["base_name"], (entry["weekday"], entry["time"]))
            if weekday and hhmm and (sub.get("update_date"), sub.get("update_time")) != (weekday, hhmm):
                sub["update_date"], sub["update_time"] = weekday, hhmm
                changed = True
            if is_newer_episode(entry["episode"], sub.get("episode", "")):
                sub["episode"] = entry["episode"]
                sub["notified_at"] = now
                changed = True
                notifications.append((server_id, {
                    "name": sub["name"],
                    "episode": entry["episode"],
                    "href": entry["href"],
                    "image": entry["image"],
                }))
            kept.append(sub)
        if kept:
            data[server_id] = kept
        else:
            data.pop(server_id)
    return changed, notifications, removed


def _air_windows(sub, now):
    """回傳這部動畫最近幾次播出的 (開始, 結束) timestamp，涵蓋跨週的情況"""
    weekday, hhmm = sub.get("update_date"), sub.get("update_time") or ""
    if not weekday or len(hhmm) != 4 or not hhmm.isdigit():
        return []
    local = datetime.datetime.fromtimestamp(now, TW_TZ)
    monday = local - datetime.timedelta(days=local.weekday())
    aired = monday.replace(hour=int(hhmm[:2]), minute=int(hhmm[2:]), second=0, microsecond=0) \
        + datetime.timedelta(days=weekday - 1)
    windows = []
    for weeks in (-1, 0, 1):
        start = (aired + datetime.timedelta(weeks=weeks)).timestamp()
        windows.append((start - FAST_POLL_BEFORE, start + FAST_POLL_AFTER))
    return windows


def seconds_until_fast_poll(data, now=None):
    """0 = 現在有動畫在播出時段且還沒抓到新集數；否則回傳距離下一個播出時段的秒數"""
    now = time.time() if now is None else now
    wait = None
    for subs in data.values():
        for sub in subs:
            for start, end in _air_windows(sub, now):
                if start <= now <= end:
                    if sub.get("notified_at", 0) < start:
                        return 0
                elif start > now and (wait is None or start - now < wait):
                    wait = start - now
    return wait


@_sub_lock
def next_poll_delay(fast_interval, normal_interval, now=None):
    wait = seconds_until_fast_poll(_load_subs(), now)
    if wait == 0:
        return fast_interval
    if wait is None:
        return normal_interval
    return max(1, min(normal_interval, wait))


def poll_updates():
    """抓一次首頁並檢查所有伺服器的訂閱，回傳 (新集數通知, 已結束而移除的動畫)"""
    html = _fetch_homepage()
    if html is None:
        return [], []
    entries = parse_timeline(html)
    if not entries:
        # 首頁改版或被擋時解析不到任何動畫，不要當成全部完結
        return [], []
    schedule = parse_schedule(html)
    with _SUB_LOCK:
        data = _load_subs()
        changed, notifications, removed = apply_updates(data, entries, schedule)
        if changed:
            _save_subs(data)
    return notifications, removed


if __name__ == "__main__":
    print(anime_get_info("ave"))
