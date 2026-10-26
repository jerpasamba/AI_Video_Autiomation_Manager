import json
import logging
import os
import hashlib
import threading
from datetime import datetime


log = logging.getLogger("upload_registry")
_registry_lock = threading.Lock()


def _root_dir():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _registry_path():
    return os.path.join(_root_dir(), "uploads.json")


def _norm(path):
    return os.path.normcase(os.path.abspath(path))


def _sha256(path, chunk_size=1024 * 1024):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def load_registry():
    p = _registry_path()
    if not os.path.exists(p):
        return {"version": 1, "items": []}
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and "items" in data:
            return data
    except Exception as e:
        log.warning("Failed to load upload registry (resetting): %s", e)
    return {"version": 1, "items": []}


def save_registry(data):
    p = _registry_path()
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        log.warning("Failed to save upload registry: %s", e)


def find_existing(video_path, platform, compute_hash=False):
    """Return existing item if we already uploaded this file to platform."""
    if not video_path:
        return None
    key = _norm(video_path)
    base_name = os.path.basename(video_path).lower()

    sha = None
    if compute_hash and os.path.exists(video_path):
        try:
            sha = _sha256(video_path)
        except Exception:
            sha = None

    with _registry_lock:
        reg = load_registry()
        for it in reg.get("items", []):
            it_plat = it.get("platform")
            if platform in ("youtube", "youtube_short"):
                if it_plat not in ("youtube", "youtube_short"):
                    continue
            elif it_plat != platform:
                continue

            if sha and it.get("sha256") == sha:
                return it

            it_path = it.get("path", "")
            # Direct path match
            if it_path == key:
                return it

            # Path without drive letter match (handles repo moved C: -> D:)
            if it_path and not it_path.startswith("http"):
                it_base = os.path.basename(it_path).lower()
                if it_base and base_name and it_base == base_name:
                    return it
                # Strip drive prefix and check path suffix
                clean_it = it_path.replace("\\", "/").lower()
                clean_key = key.replace("\\", "/").lower()
                if ":" in clean_it and ":" in clean_key:
                    if clean_it.split(":", 1)[1] == clean_key.split(":", 1)[1]:
                        return it

    return None


def get_platforms_for_video(video_path):
    """Return a dictionary of platforms this video is already uploaded to, with their URL."""
    if not video_path:
        return {}
    base_name = os.path.basename(video_path).lower()
    clean_key = _norm(video_path).replace("\\", "/").lower()
    uploaded_platforms = {}

    with _registry_lock:
        reg = load_registry()
        for it in reg.get("items", []):
            it_plat = it.get("platform")
            if not it_plat:
                continue
            it_path = (it.get("path") or "").replace("\\", "/").lower()
            it_base = os.path.basename(it_path).lower()

            matched = False
            if it_path == clean_key:
                matched = True
            elif it_base and base_name and it_base == base_name:
                matched = True
            elif ":" in it_path and ":" in clean_key:
                if it_path.split(":", 1)[1] == clean_key.split(":", 1)[1]:
                    matched = True

            if matched:
                uploaded_platforms[it_plat] = {
                    "url": it.get("url"),
                    "remote_id": it.get("remote_id"),
                    "uploaded_at": it.get("uploaded_at"),
                    "metrics": it.get("metrics") or {},
                }

    return uploaded_platforms


def get_uploaded_items_for_platform(platform):
    """Return all recorded uploads for a given platform from uploads.json."""
    with _registry_lock:
        reg = load_registry()
        items = []
        for it in reg.get("items", []):
            it_plat = it.get("platform")
            if platform in ("youtube", "youtube_short"):
                if it_plat in ("youtube", "youtube_short"):
                    items.append(it)
            elif it_plat == platform:
                items.append(it)
        return list(reversed(items))



def record_upload(video_path, platform, remote_id=None, url=None, sha256=None, extra=None, metrics=None):
    if video_path and not video_path.startswith("http"):
        key = _norm(video_path)
    else:
        key = video_path or ""
    try:
        st = os.stat(video_path)
        size = st.st_size
        mtime = int(st.st_mtime)
    except Exception:
        size = None
        mtime = None

    item = {
        "path": key,
        "platform": platform,
        "remote_id": remote_id,
        "url": url,
        "sha256": sha256,
        "size": size,
        "mtime": mtime,
        "uploaded_at": datetime.utcnow().isoformat() + "Z",
    }
    if extra:
        item["extra"] = extra
    if metrics:
        item["metrics"] = metrics

    with _registry_lock:
        reg = load_registry()
        reg.setdefault("items", []).append(item)
        save_registry(reg)

    return item


def clear_platform(platform):
    """Remove all registry items for a platform."""
    if not platform:
        return 0
    with _registry_lock:
        reg = load_registry()
        before = len(reg.get("items", []) or [])
        reg["items"] = [it for it in reg.get("items", []) if it.get("platform") != platform]
        save_registry(reg)
        return before - len(reg.get("items", []) or [])


def update_item_metrics(video_path, platform, metrics):
    """Update view count, like count, and verification status for an upload."""
    if not video_path:
        return False
    key = _norm(video_path)
    with _registry_lock:
        reg = load_registry()
        updated = False
        for it in reg.get("items", []):
            if it.get("path") == key and it.get("platform") == platform:
                it["metrics"] = metrics
                updated = True
                break
        if updated:
            save_registry(reg)
        return updated

