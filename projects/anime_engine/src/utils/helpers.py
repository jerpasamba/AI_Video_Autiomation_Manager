import json
import os
import re


def load_config(config_path="config.json"):
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config, config_path="config.json"):
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)


def sanitize_filename(name):
    return re.sub(r'[<>:"/\\|?*]', "_", name)


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)
    return path


def format_duration(seconds):
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"
