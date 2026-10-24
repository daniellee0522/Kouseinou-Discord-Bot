import json
import config
from utils.json_cache import load_json_cached


def change_permission(server_id, arg):
    if server_id == None:
        return False
    with open(config.DATA_DIR / 'embed_permission.json', 'r', encoding='utf8') as f:
        data = json.load(f)
    server_id = str(server_id)
    if server_id in data.keys():
        if arg in data[server_id].keys():
            if data[server_id][arg] == 0:
                data[server_id][arg] = 1
                with open(config.DATA_DIR / 'embed_permission.json', 'w', encoding='utf8') as f:
                    json.dump(
                        data, f, ensure_ascii=False, indent=4)
                return "已關閉"
            else:
                data[server_id][arg] = 0
                with open(config.DATA_DIR / 'embed_permission.json', 'w', encoding='utf8') as f:
                    json.dump(
                        data, f, ensure_ascii=False, indent=4)
                return "已開啟"
        else:
            data[server_id][arg] = 1
            with open(config.DATA_DIR / 'embed_permission.json', 'w', encoding='utf8') as f:
                json.dump(
                    data, f, ensure_ascii=False, indent=4)
            return "已關閉"
    else:
        data[server_id] = {arg: 1}
        with open(config.DATA_DIR / 'embed_permission.json', 'w', encoding='utf8') as f:
            json.dump(
                data, f, ensure_ascii=False, indent=4)
        return "已關閉"


def is_embed_ban(server_id, arg):
    data = load_json_cached(config.DATA_DIR / 'embed_permission.json', {})
    return data.get(str(server_id), {}).get(arg) == 1
