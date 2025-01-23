import json


def change_permission(server_id, arg):
    if server_id == None:
        return False
    with open('json/embed_permission.json', 'r', encoding='utf8') as f:
        data = json.load(f)
    server_id = str(server_id)
    if server_id in data.keys():
        if arg in data[server_id].keys():
            if data[server_id][arg] == 0:
                data[server_id][arg] = 1
                with open('json/embed_permission.json', 'w', encoding='utf8') as f:
                    json.dump(
                        data, f, ensure_ascii=False, indent=4)
                return "已關閉"
            else:
                data[server_id][arg] = 0
                with open('json/embed_permission.json', 'w', encoding='utf8') as f:
                    json.dump(
                        data, f, ensure_ascii=False, indent=4)
                return "已開啟"
        else:
            data[server_id][arg] = 1
            with open('json/embed_permission.json', 'w', encoding='utf8') as f:
                json.dump(
                    data, f, ensure_ascii=False, indent=4)
            return "已關閉"
    else:
        data[server_id] = {arg: 1}
        with open('json/embed_permission.json', 'w', encoding='utf8') as f:
            json.dump(
                data, f, ensure_ascii=False, indent=4)
        return "已關閉"


def is_embed_ban(server_id, arg):
    server_id = str(server_id)
    with open('json/embed_permission.json', 'r', encoding='utf8') as f:
        data = json.load(f)
    if server_id in data.keys():
        if arg in data[server_id]:
            if data[server_id][arg] == 1:
                return True
            else:
                return False
        else:
            return False

    else:
        return False
