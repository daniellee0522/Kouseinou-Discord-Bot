import time
import asyncio
import inspect
from functools import wraps


def async_ttl_cache(ttl_seconds=300, maxsize=256, key_arg="digit"):
    """簡單的記憶體 TTL 快取，給查番號這類短時間內容易被重複查詢的 async function 用。
    用 key_arg 指定的參數當快取 key（忽略 session 之類的物件參數，同一個番號不會因為
    傳入的 session 物件不同就被當成不同的快取項）。只快取成功回傳的結果，丟例外的
    不快取，避免暫時性錯誤被記住太久。"""

    def decorator(func):
        cache = {}
        locks = {}
        params = list(inspect.signature(func).parameters)
        key_index = params.index(key_arg) if key_arg in params else None

        @wraps(func)
        async def wrapper(*args, **kwargs):
            if key_arg in kwargs:
                raw_key = kwargs[key_arg]
            elif key_index is not None and key_index < len(args):
                raw_key = args[key_index]
            else:
                raw_key = args
            key = str(raw_key).strip().lower()

            now = time.monotonic()
            cached = cache.get(key)
            if cached and cached[0] > now:
                return cached[1]

            lock = locks.setdefault(key, asyncio.Lock())
            async with lock:
                cached = cache.get(key)
                if cached and cached[0] > now:
                    return cached[1]

                result = await func(*args, **kwargs)

                cache[key] = (time.monotonic() + ttl_seconds, result)
                if len(cache) > maxsize:
                    oldest_key = min(cache, key=lambda k: cache[k][0])
                    cache.pop(oldest_key, None)
                    locks.pop(oldest_key, None)
                return result

        return wrapper

    return decorator
