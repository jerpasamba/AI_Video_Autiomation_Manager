import os
import sys
import json

MANHWA_PATH = None


def _resolve_path(config):
    global MANHWA_PATH
    if MANHWA_PATH:
        return MANHWA_PATH
    rel = config.get("manhwa_project_path", "projects/manhwa_engine")
    MANHWA_PATH = os.path.abspath(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), rel
    ))
    return MANHWA_PATH


def get_chapter_status(chapter_num, config):
    project_path = _resolve_path(config)
    out_dir = os.path.join(project_path, "output", "Final", f"ch{chapter_num:02d}")
    video_path = os.path.join(out_dir, f"chapter_{chapter_num:02d}_video.mp4")
    thumb_path = os.path.join(out_dir, "thumbnail.jpg")
    script_path = os.path.join(out_dir, "script.json")
    meta_path = os.path.join(out_dir, "youtube_meta.json")

    status = "not_started"
    if os.path.exists(video_path):
        status = "generated"
    elif os.path.exists(script_path):
        status = "in_progress"

    has_empty_script = False
    if os.path.exists(script_path):
        try:
            with open(script_path, encoding="utf-8") as f:
                script = json.load(f)
            total_scenes = len(script.get("scenes", []))
            total_panels = sum(len(s.get("panels", [])) for s in script.get("scenes", []))
            if total_scenes == 0 or total_panels == 0:
                has_empty_script = True
        except Exception:
            pass

    return {
        "chapter": chapter_num,
        "status": status,
        "has_video": os.path.exists(video_path),
        "has_thumbnail": os.path.exists(thumb_path),
        "has_meta": os.path.exists(meta_path),
        "has_empty_script": has_empty_script,
        "video_path": video_path if os.path.exists(video_path) else None,
        "thumbnail_path": thumb_path if os.path.exists(thumb_path) else None,
    }


def get_all_chapters(config):
    project_path = _resolve_path(config)
    bible_path = os.path.join(project_path, "story_bible.json")
    total = 0
    chapters = []
    if os.path.exists(bible_path):
        with open(bible_path, encoding="utf-8") as f:
            bible = json.load(f)
        total = len(bible.get("chapters", []))
    else:
        total = 7

    for i in range(1, total + 1):
        chapters.append(get_chapter_status(i, config))
    return chapters


def generate_chapter(chapter_num, progress_cb, config):
    project_path = _resolve_path(config)
    sys.path.insert(0, os.path.join(project_path, "scripts"))
    sys.path.insert(0, os.path.join(project_path, "scripts", "final"))
    sys.path.insert(0, project_path)

    from run_chapter import run_chapter as _run_chapter

    steps = [
        ("script", 12),
        ("panels", 25),
        ("voice", 37),
        ("subs", 50),
        ("video", 62),
        ("render", 75),
        ("meta", 87),
        ("thumb", 100),
    ]

    flags_sequence = [
        {"script"},
        {"panels"},
        {"voice", "subs"},
        {"video", "render"},
        {"meta", "thumb"},
    ]

    progress_cb(0, "Starting manhwa chapter pipeline...")

    out_dir = os.path.join(project_path, "output", "Final", f"ch{chapter_num:02d}")
    script_path = os.path.join(out_dir, "script.json")
    os.makedirs(out_dir, exist_ok=True)

    if not os.path.exists(script_path):
        progress_cb(5, "Generating chapter script...")
        old_cwd = os.getcwd()
        os.chdir(project_path)
        try:
            _run_chapter(chapter_num, {"script"})
        finally:
            os.chdir(old_cwd)
        progress_cb(12, "Script generated")

    with open(script_path, encoding="utf-8") as f:
        script = json.load(f)
    total_scenes = len(script.get("scenes", []))
    total_panels = sum(len(s.get("panels", [])) for s in script.get("scenes", []))
    if total_scenes == 0 or total_panels == 0:
        raise RuntimeError(
            f"Chapter {chapter_num} script has {total_scenes} scenes and {total_panels} panels"
            " - possible Gemini quota exhaustion, will retry on next app start"
        )

    progress_cb(12, f"Generating {total_panels} panel images...")
    old_cwd = os.getcwd()
    os.chdir(project_path)
    try:
        _run_chapter(chapter_num, {"panels"})
    finally:
        os.chdir(old_cwd)
    progress_cb(25, "Panels generated")

    progress_cb(25, "Generating voice narration...")
    os.chdir(project_path)
    try:
        _run_chapter(chapter_num, {"voice"})
    finally:
        os.chdir(old_cwd)
    progress_cb(37, "Voice generated")

    progress_cb(37, "Syncing subtitles...")
    os.chdir(project_path)
    try:
        _run_chapter(chapter_num, {"subs"})
    finally:
        os.chdir(old_cwd)
    progress_cb(50, "Subtitles synced")

    progress_cb(50, "Creating panel video with camera motion...")
    os.chdir(project_path)
    try:
        _run_chapter(chapter_num, {"video", "render"})
    finally:
        os.chdir(old_cwd)
    progress_cb(75, "Video rendered")

    progress_cb(75, "Generating YouTube metadata...")
    os.chdir(project_path)
    try:
        _run_chapter(chapter_num, {"meta"})
    finally:
        os.chdir(old_cwd)
    progress_cb(87, "Metadata generated")

    progress_cb(87, "Generating thumbnail...")
    os.chdir(project_path)
    try:
        _run_chapter(chapter_num, {"thumb"})
    finally:
        os.chdir(old_cwd)
    progress_cb(100, "Chapter complete!")

    return get_chapter_status(chapter_num, config)
