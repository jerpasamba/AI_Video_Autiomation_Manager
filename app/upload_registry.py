import json
import os
import hashlib
from datetime import datetime


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
    except Exception:
        pass
    return {"version": 1, "items": []}


def save_registry(data):
    p = _registry_path()
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def find_existing(video_path, platform, compute_hash=False):
    """Return existing item if we already uploaded this file to platform."""
    if not video_path:
        return None
    key = _norm(video_path)
    try:
        st = os.stat(video_path)
    except Exception:
        st = None

    sha = None
    if compute_hash and os.path.exists(video_path):
        try:
            sha = _sha256(video_path)
        except Exception:
            sha = None

    reg = load_registry()
    for it in reg.get("items", []):
        if it.get("platform") != platform:
            continue
        if sha and it.get("sha256") == sha:
            return it
        if it.get("path") == key:
            # If file changed, allow re-upload.
            if st and it.get("size") == st.st_size and it.get("mtime") == int(st.st_mtime):
                return it
    return None


def record_upload(video_path, platform, remote_id=None, url=None, sha256=None, extra=None):
    reg = load_registry()
    key = _norm(video_path) if video_path else ""
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

    reg.setdefault("items", []).append(item)
    save_registry(reg)
    return item
