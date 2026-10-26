import os
import sys
import json

ANIME_SHORTS_PATH = None


def _resolve_path(config):
    global ANIME_SHORTS_PATH
    if ANIME_SHORTS_PATH:
        return ANIME_SHORTS_PATH
    rel = config.get("anime_shorts_path", "projects/anime_engine")
    ANIME_SHORTS_PATH = os.path.abspath(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), rel
    ))
    return ANIME_SHORTS_PATH


def _setup_imports(config):
    path = _resolve_path(config)
    if path not in sys.path:
        sys.path.insert(0, path)


def get_generated_shorts(config):
    path = _resolve_path(config)
    config_path = config.get("anime_shorts_config",
                             os.path.join(path, "src", "config.json"))
    if os.path.exists(config_path):
        with open(config_path) as f:
            anime_cfg = json.load(f)
        output_dir = anime_cfg.get("output_dir", "output")
        shorts_dir = os.path.join(path, output_dir, "shorts")
    else:
        shorts_dir = os.path.join(path, "output", "shorts")

    results = []
    if os.path.exists(shorts_dir):
        for fname in os.listdir(shorts_dir):
            if fname.endswith("_shorts.mp4"):
                fpath = os.path.join(shorts_dir, fname)
                title = fname.replace("_shorts.mp4", "").replace("_", " ").title()
                description = ""
                tags = ["anime", "shorts", "highlight"]
                # Load persisted metadata if available
                meta_path = fpath.replace("_shorts.mp4", "_shorts_meta.json")
                if os.path.exists(meta_path):
                    try:
                        with open(meta_path, encoding="utf-8") as f:
                            meta = json.load(f)
                        title = meta.get("title", title)
                        description = meta.get("description", "")
                        tags = meta.get("tags", tags)
                    except Exception:
                        pass
                results.append({
                    "path": fpath,
                    "title": title,
                    "description": description,
                    "tags": tags,
                    "size_mb": os.path.getsize(fpath) / (1024 * 1024),
                    "modified": os.path.getmtime(fpath),
                })
    return sorted(results, key=lambda x: x["modified"], reverse=True)


def generate_from_url(url, progress_cb, config):
    _setup_imports(config)
    from src.config import Config
    from src.pipeline import Pipeline

    cfg_path = config.get("anime_shorts_config",
                          os.path.join(_resolve_path(config), "src", "config.json"))
    anime_cfg = Config(cfg_path)

    progress_cb(5, "Initializing pipeline...")
    pipeline = Pipeline(anime_cfg)

    progress_cb(10, "Downloading video...")

    def _progress(msg):
        if "..." in msg or "Done" in msg or "found" in msg or "clip" in msg:
            pct = min(90, pipeline._current_progress if hasattr(pipeline, '_current_progress') else 50)
            progress_cb(pct, msg)

    old_cwd = os.getcwd()
    os.chdir(_resolve_path(config))
    try:
        results = pipeline.process_url(url, progress_callback=_progress)
    finally:
        os.chdir(old_cwd)

    if results:
        progress_cb(95, f"Generated {len(results)} shorts")
        progress_cb(100, "Complete")
    else:
        progress_cb(100, "No clips generated")

    return results


def auto_search_generate(config, progress_cb):
    _setup_imports(config)
    from src.config import Config
    from src.downloader.youtube import YouTubeDownloader

    cfg_path = config.get("anime_shorts_config",
                          os.path.join(_resolve_path(config), "src", "config.json"))
    anime_cfg = Config(cfg_path)

    progress_cb(5, "Searching for videos...")
    downloader = YouTubeDownloader(
        output_dir=os.path.join(anime_cfg["output_dir"], "downloads")
    )

    try:
        results = downloader.search_auto(progress_callback=progress_cb)
        if results:
            for url in results[:3]:
                progress_cb(20, f"Generating from: {url[:60]}...")
                generate_from_url(url, progress_cb, config)
            progress_cb(100, "Auto-generation complete")
        else:
            progress_cb(100, "No videos found")
    except Exception as e:
        progress_cb(100, f"Search failed: {e}")
