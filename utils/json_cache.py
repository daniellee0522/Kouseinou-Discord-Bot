import json
import os

# path -> (mtime_ns, size, data)：檔案沒變就直接用記憶體裡的內容，
# 避免 on_message 這種熱路徑每則訊息都重新讀檔、解析 JSON
_cache = {}


def load_json_cached(path, default=None):
    """讀 JSON 檔，依 mtime／大小判斷有沒有改過；檔案不存在或壞掉回傳 default。
    回傳的物件是共用的快取，呼叫端只能讀不能改。"""
    path = os.fspath(path)
    try:
        st = os.stat(path)
    except FileNotFoundError:
        return default
    stamp = (st.st_mtime_ns, st.st_size)
    cached = _cache.get(path)
    if cached is not None and cached[0] == stamp:
        return cached[1]
    try:
        with open(path, 'r', encoding='utf8') as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return default if cached is None else cached[1]
    _cache[path] = (stamp, data)
    return data
