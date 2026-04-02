import json
import random
from pathlib import Path
from functions.slot import Gacha, check_lock # 假設原本的導入路徑
import config

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
        
    return {"feed": feed, "stone": stone, "result": result}, "ok"