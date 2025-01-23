import json
NOTIFY_FILE = 'json/notifies.json'
def add_notify_to_file(self,data):
    with open(NOTIFY_FILE, 'r') as f:
        notifies = json.load(f)
    notifies.append(data)
    with open(NOTIFY_FILE, 'w') as f:
        json.dump(notifies, f)
