import json, os

CONFIG_PATH = "./config/channels.json"

def load_channels():
    if not os.path.exists(CONFIG_PATH) or os.path.getsize(CONFIG_PATH) == 0:
        return {"types": []}

    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

def save_channels(data):
    with open(CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=4)
