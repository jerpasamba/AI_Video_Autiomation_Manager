import json
import os
import threading
from datetime import datetime


class Monitor:
    def __init__(self, config, monitor_path=None):
        self.config = config
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self._path = monitor_path or os.path.join(root, "monitor.json")
        self._lock = threading.Lock()
        self._data = self._load()

    def _load(self):
        try:
            if os.path.exists(self._path):
                with open(self._path) as f:
                    return json.load(f)
        except Exception:
            pass
        return {
            "generated": {"manhwa": 0, "anime": 0, "minecraft": 0},
            "uploaded": {"facebook": {"ok": 0, "fail": 0}, "youtube": {"ok": 0, "fail": 0}},
            "failed_generation": {"manhwa": 0, "anime": 0, "minecraft": 0},
            "activity": [],
        }

    def _save(self):
        try:
            with open(self._path, "w") as f:
                json.dump(self._data, f, indent=2)
        except Exception:
            pass

    def increment_generated(self, pipeline):
        with self._lock:
            if pipeline in self._data["generated"]:
                self._data["generated"][pipeline] += 1
            self._add_activity(f"{pipeline.title()} video generated")
            self._save()

    def increment_uploaded(self, platform, success=True):
        with self._lock:
            key = "ok" if success else "fail"
            if platform in self._data["uploaded"]:
                self._data["uploaded"][platform][key] += 1
            label = "uploaded" if success else "upload FAILED"
            self._add_activity(f"Facebook {label}")
            self._save()

    def increment_failed_generation(self, pipeline):
        with self._lock:
            if pipeline in self._data["failed_generation"]:
                self._data["failed_generation"][pipeline] += 1
            self._add_activity(f"{pipeline.title()} generation FAILED")
            self._save()

    def _add_activity(self, text):
        self._data["activity"].insert(0, {
            "time": datetime.now().isoformat(),
            "text": text,
        })
        if len(self._data["activity"]) > 100:
            self._data["activity"] = self._data["activity"][:100]

    def get_counters(self):
        with self._lock:
            return {
                "generated": dict(self._data["generated"]),
                "uploaded": {k: dict(v) for k, v in self._data["uploaded"].items()},
                "failed_generation": dict(self._data["failed_generation"]),
            }

    def get_activity(self, limit=20):
        with self._lock:
            return list(self._data["activity"][:limit])

    def reset(self):
        with self._lock:
            self._data = self._load()
            for key in self._data["generated"]:
                self._data["generated"][key] = 0
            for platform in self._data["uploaded"]:
                self._data["uploaded"][platform]["ok"] = 0
                self._data["uploaded"][platform]["fail"] = 0
            for key in self._data["failed_generation"]:
                self._data["failed_generation"][key] = 0
            self._data["activity"] = []
            self._save()
