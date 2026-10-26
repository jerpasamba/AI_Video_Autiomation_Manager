import os
import re
import sys
import json

MOVIEREELS_PATH = None


def _resolve_path(config):
    global MOVIEREELS_PATH
    if MOVIEREELS_PATH:
        return MOVIEREELS_PATH
    rel = config.get("moviereels_path", "projects/moviereels_engine")
    MOVIEREELS_PATH = os.path.abspath(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), rel
    ))
    return MOVIEREELS_PATH


def _setup_imports(config):
    path = _resolve_path(config)
    if path not in sys.path:
        sys.path.insert(0, path)


def get_generated_reels(config):
    path = _resolve_path(config)
    output_dir = os.path.join(path, "output")
    results = []
    if os.path.exists(output_dir):
        for fname in os.listdir(output_dir):
            if fname.endswith(".mp4") and not fname.startswith("_") and not fname.endswith("_raw.mp4"):
                fpath = os.path.join(output_dir, fname)
                meta = _load_meta(fpath)
                results.append({
                    "path": fpath,
                    "hook": meta.get("hook", ""),
                    "topic": meta.get("topic", fname.replace(".mp4", "").replace("_", " ").title()),
                    "duration_sec": meta.get("estimated_duration_seconds", 0),
                    "size_mb": os.path.getsize(fpath) / (1024 * 1024),
                    "modified": os.path.getmtime(fpath),
                    "title": meta.get("title", meta.get("hook", "")),
                    "description": meta.get("description", ""),
                    "tags": meta.get("tags", []),
                })
    return sorted(results, key=lambda x: x["modified"], reverse=True)


def _load_meta(video_path):
    meta_file = os.path.splitext(video_path)[0] + "_meta.json"
    if os.path.exists(meta_file):
        try:
            with open(meta_file, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_meta(video_path, data):
    meta_file = os.path.splitext(video_path)[0] + "_meta.json"
    try:
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


import importlib.util

def _load_engine(config):
    path = _resolve_path(config)
    main_file = os.path.join(path, "main.py")
    if not os.path.exists(main_file):
        raise FileNotFoundError(f"MovieReels engine main.py not found at: {main_file}")
    spec = importlib.util.spec_from_file_location("moviereels_engine", main_file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def generate_reel(topic, progress_cb, config):
    _setup_imports(config)
    moviereels = _load_engine(config)

    output_dir = os.path.join(_resolve_path(config), "output")

    search_term = None if topic in (None, "", "__auto__") else topic
    progress_cb(5, "Searching movie clips..." if not search_term else f"Searching: {search_term[:60]}...")
    result = moviereels.fetch_movie_clip(search_term=search_term, output_dir=output_dir)
    output_path = result["path"]
    hook = result["title"]

    progress_cb(85, f"Downloaded: {hook[:60]}")
    progress_cb(95, "Finalizing...")

    safe_title = re.sub(r'[^\w \-_]', "", hook).strip()[:80] or "Movie Clip"
    title = f"Movie Reel | {safe_title} | ZeroBalanceManhwa"
    description = (
        f"Epic movie clip in vertical format!\n\n"
        f"{hook}\n\n"
        f"Source: {result.get('source_url', '')}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎬 ZeroBalanceManhwa\n"
        f"Bringing you the best movie scenes in cinematic 9:16 format.\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"#MovieClips #Cinematic #ZeroBalanceManhwa #MovieReels #MovieScenes"
    )
    fb_tags = ["movie", "reels", "movieclips", "cinematic", "ZeroBalanceManhwa", "entertainment", "films"]

    _save_meta(output_path, {
        "topic": topic or "auto movie clip",
        "hook": hook,
        "title": title,
        "description": description,
        "tags": fb_tags,
        "source_url": result.get("source_url", ""),
        "estimated_duration_seconds": result.get("duration_sec", 0),
        "music": result.get("music", ""),
    })

    progress_cb(100, f"Movie clip: {os.path.basename(output_path)}")
    return {"path": output_path, "hook": hook}
