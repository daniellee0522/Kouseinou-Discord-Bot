import datetime
import json
import random
from pathlib import Path
from functions.slot import Gacha, check_lock # 假設原本的導入路徑
import config

# 新制（日服 2026/7/29 起的「招募充能」，取代 200 點兌換）：每抽一次 PU 招募充能 +1，
# 第 100 抽必定 ★3（50% 是 PU），第 200 抽必定 PU；只有抽到 PU 才歸零（同一次十連裡之後的抽從 1 重新算），
# 換卡池也會繼承。單抽機率不變。
# 國際服預定 2026/11/10 維護後才改版（名稱叫「招募積分」，細節還沒公布），之前維持舊制（沒有保底、200 抽一井）。
# 維護結束時間沒公告，先抓台灣時間中午；國際服公布規則後可能要再調整
CHARGE_SSR = 100
CHARGE_PU = 200
NEW_SYSTEM_FROM = datetime.datetime(2026, 11, 10, 12, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=8)))


def new_system_active(now=None):
    return (now or datetime.datetime.now(datetime.timezone.utc)) >= NEW_SYSTEM_FROM


def apply_charge(result, charge):
    """依招募充能套用保底，回傳 (套用後的結果, 新的充能, 這次觸發的保底 [(第幾抽, 結果)])。
    結果："PU"（200 抽保底）、"SSR_PU"（100 抽保底抽中 PU）、"SSR"（100 抽保底沒中 PU）"""
    result = list(result)
    triggered = []
    for i, res in enumerate(result):
        charge += 1
        if charge >= CHARGE_PU and res != 4:
            result[i] = 4
            triggered.append((charge, "PU"))
        elif charge == CHARGE_SSR and res != 4:
            result[i] = 4 if random.random() < 0.5 else 3
            triggered.append((charge, "SSR_PU" if result[i] == 4 else "SSR"))
        if result[i] == 4:
            charge = 0
    return result, charge, triggered


def process_gacha_data(user_id, channel_id):
    # 檢查鎖定與冷卻 (原本 bot.py 裡的邏輯)
    if check_lock(channel_id):
        return None, "lock"

    # 讀取 PU 資訊
    with open(config.DATA_DIR / 'pu.json', 'r', encoding='utf8') as f:
        tdata = json.load(f)
    
    current_pu = next((k for k, v in tdata.items() if v is True), None)
    # 複製一份排除掉當前 PU 的清單供隨機 SSR 使用
    other_ssr = {k: v for k, v in tdata.items() if k != current_pu}

    # 執行抽卡機制
    result = Gacha(3, 18.5, 78.5, [0.7, 0.031507])
    
    # 處理統計數據
    gacha_file = config.DATA_DIR / 'gacha.json'
    with open(gacha_file, 'r', encoding='utf8') as f:
        data = json.load(f)
    
    user = data.get(str(user_id), {"PU": 0, "SSR": 0, "SR": 0, "R": 0, "total": 0})
    new_system = new_system_active()
    triggered = []
    if new_system:
        result, user["charge"], triggered = apply_charge(result, user.get("charge", 0))
    
    feed, stone = "", ""
    for i, res in enumerate(result):
        if res == 3: # SSR
            feed += "<:SSR:1075797446598336603>"
            stone += ":new:"
        elif res == 2: # SR
            feed += "<:SR:1075797417787662398>"
            stone += "<:moji:1075798877573230623>x10"
        elif res == 1: # R
            feed += "<:R_:1075797383184646265>"
            stone += "<:moji:1075798877573230623>x1"
        elif res == 4: # PU
            feed += current_pu if current_pu else "???"
            stone += ":new:"
        elif res in [5, 6]: # 其他 SSR
            key = random.choice(list(other_ssr.keys())) if other_ssr else "???"
            feed += key
            stone += ":new:"
        
        if i == 4:
            feed += "\n"
            stone += "\n"

    # 更新數據
    user["PU"] += result.count(4)
    user["SSR"] += (result.count(3) + sum(result.count(i) for i in range(4, 7)))
    user["SR"] += result.count(2)
    user["R"] += result.count(1)
    user["total"] += 10
    
    data[str(user_id)] = user
    with open(gacha_file, 'w', encoding='utf8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
        
    return {"feed": feed, "stone": stone, "result": result, "pu": current_pu, "new_system": new_system,
            "charge": user.get("charge", 0), "triggered": triggered, "total": user["total"]}, "ok"