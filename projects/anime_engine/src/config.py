import json
import os

DEFAULT_CONFIG = {
    "output_dir": "output",
    "intro_text": "ZeroBalanceManhwa",
    "outro_text": "Subscribe for more!",
    "background_music_volume": 0.3,
    "bgm_playlist_url": "",
    "voiceover_enabled": False,
    "logo_path": "assets/logo.png",
    "channel_name": "ZeroBalanceManhwa",
    "channel_handle": "@ZeroBalanceManhwa",
    "youtube": {
        "client_secret_file": "",
        "token_file": "youtube_token.json",
        "upload_enabled": False,
        "default_tags": ["anime", "shorts", "highlights"],
        "default_category": "22"
    },
    "combine_segments": True,
    "scene_detection": {
        "scene_threshold": 0.4,
        "top_n_clips": 5
    }
}


class Config:
    def __init__(self, path="config.json"):
        self.path = path
        self._data = self._load()

    def _load(self):
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
        return dict(DEFAULT_CONFIG)

    def reload(self):
        self._data = self._load()

    def save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=4)

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value

    def get(self, key, default=None):
        return self._data.get(key, default)

    @property
    def data(self):
        return self._data
