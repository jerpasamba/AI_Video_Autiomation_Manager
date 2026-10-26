import os
import sys
import asyncio
import random
import json
import uuid

MINECRAFT_PATH = None


def _resolve_path(config):
    global MINECRAFT_PATH
    if MINECRAFT_PATH:
        return MINECRAFT_PATH
    rel = config.get("minecraft_path", "projects/minecraft_engine")
    MINECRAFT_PATH = os.path.abspath(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), rel
    ))
    return MINECRAFT_PATH


def _setup_imports(config):
    path = _resolve_path(config)
    if path not in sys.path:
        sys.path.insert(0, path)


def _load_meta(video_path):
    meta_file = os.path.splitext(video_path)[0] + "_meta.json"
    if os.path.exists(meta_file):
        try:
            with open(meta_file, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_meta(video_path, title, description, story_text):
    meta_file = os.path.splitext(video_path)[0] + "_meta.json"
    try:
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump({
                "title": title,
                "description": description,
                "story_text": story_text,
                "tags": ["reallife", "storytime", "emotional", "shorts", "relationship",
                         "heartbreak", "truestory", "lifelessons", "minecraft", "ai"],
            }, f, indent=2)
    except Exception:
        pass


def get_generated_stories(config):
    path = _resolve_path(config)
    output_dir = os.path.join(path, "output")
    results = []
    if os.path.exists(output_dir):
        for fname in os.listdir(output_dir):
            if fname.endswith(".mp4"):
                fpath = os.path.join(output_dir, fname)
                meta = _load_meta(fpath)
                results.append({
                    "path": fpath,
                    "title": meta.get("title") or fname.replace(".mp4", "").replace("_", " ").title(),
                    "description": meta.get("description", ""),
                    "tags": meta.get("tags", ["reallife", "storytime", "emotional", "shorts"]),
                    "size_mb": os.path.getsize(fpath) / (1024 * 1024),
                    "modified": os.path.getmtime(fpath),
                })
    return sorted(results, key=lambda x: x["modified"], reverse=True)


_AI_PREFIXES = [
    "here is", "here's", "i'll tell", "let me tell", "this is a story",
    "i want to share", "let me share", "here's a story", "here is a story",
    "i have a story", "so here's", "so here is", "the story goes",
    "imagine this", "picture this", "have you ever", "you know that feeling",
    "i remember", "this happened", "it all started", "the story begins",
]


def _strip_ai_prefixes(text):
    lowered = text.lower().strip()
    for prefix in _AI_PREFIXES:
        if lowered.startswith(prefix):
            stripped = text[len(prefix):].strip().lstrip(",").strip()
            if len(stripped) > 15:
                return stripped
    return text


def _generate_catchy_title(story_text, prompt):
    """Generate a catchy YouTube/Facebook title from the story content."""
    lines = story_text.strip().split("\n")

    for line in lines:
        line = line.strip()
        if not line or len(line) < 15:
            continue
        clean = line.replace("\u201c", "").replace("\u201d", "").replace('"', "").strip()
        clean = _strip_ai_prefixes(clean)
        if clean.endswith((".", "!", "?")):
            clean = clean[:-1]
        if len(clean) > 95:
            clean = clean[:95].rsplit(" ", 1)[0]
        if len(clean) >= 20:
            return clean.strip()

    return None


def _generate_description(story_text, title):
    """Generate a rich description with hashtags for YouTube and Facebook."""
    first_para = story_text.strip().split("\n\n")[0][:300] if story_text.strip() else ""
    return (
        f"{title}\n\n"
        f"{first_para}\n\n"
        f"Has this ever happened to you? Share your thoughts in the comments below. "
        f"Don't forget to like and subscribe for more real-life stories!\n\n"
        f"#RealStory #TrueStory #Relationship #Heartbreak #LifeLessons #StoryTime #"
        f"Emotional #Relatable #DeepTalk #Shorts\n"
    )


import importlib.util

def _load_engine(config):
    path = _resolve_path(config)
    main_file = os.path.join(path, "main.py")
    if not os.path.exists(main_file):
        raise FileNotFoundError(f"Minecraft engine main.py not found at: {main_file}")
    spec = importlib.util.spec_from_file_location("minecraft_engine", main_file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def generate_minecraft_story(prompt, progress_cb, config):
    _setup_imports(config)
    mc_main = _load_engine(config)

    output_dir = os.path.join(_resolve_path(config), "output")
    os.makedirs(output_dir, exist_ok=True)

    path = _resolve_path(config)
    assets_dir = os.path.join(path, "assets")
    parkour_videos = []
    if os.path.isdir(assets_dir):
        for fname in os.listdir(assets_dir):
            if fname.endswith(".mp4"):
                parkour_videos.append(os.path.join(assets_dir, fname))

    if not parkour_videos:
        progress_cb(100, "No parkour video found in assets/")
        return None

    parkour_video = random.choice(parkour_videos)

    class Args:
        def __init__(self, prompt_val, parkour_val, out_dir):
            self.prompt = prompt_val
            self.story = None
            self.system = None
            self.parkour_video = parkour_val
            self.output = os.path.join(out_dir, f"story_{uuid.uuid4().hex[:8]}.mp4")
            self.voice = "en-US-JennyNeural"

    args = Args(prompt, parkour_video, output_dir)

    progress_cb(10, "Generating story...")
    story_text = mc_main.generate_story(args.prompt, args.system)
    progress_cb(30, f"Story generated ({len(story_text)} chars)")

    progress_cb(30, "Generating TTS audio and subtitles...")
    audio_path = args.output.replace(".mp4", "_tts.mp3")

    async def run_tts():
        submaker = await mc_main.generate_tts(story_text, args.voice, audio_path)
        return submaker

    submaker = asyncio.run(run_tts())
    progress_cb(60, "TTS generated")

    progress_cb(60, "Building subtitle file...")
    srt_content = submaker.get_srt()
    if not srt_content.strip():
        progress_cb(100, "No subtitles generated")
        return None

    ass_content = mc_main.srt_to_ass(srt_content)
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".ass", delete=False, mode="w", encoding="utf-8") as f:
        f.write(ass_content)
        ass_path = f.name

    lines = srt_content.strip().split("\n")
    last_time = None
    for line in lines:
        if "-->" in line:
            last_time = line.split("-->")[1].strip().replace(",", ".")
    if last_time:
        parts = last_time.split(":")
        tts_duration = int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2]) + 1
    else:
        tts_duration = 30

    progress_cb(70, f"Compositing video ({tts_duration:.0f}s duration)...")
    old_cwd = os.getcwd()
    os.chdir(path)
    try:
        mc_main.build_ffmpeg(parkour_video, audio_path, ass_path, args.output, tts_duration)
    finally:
        os.chdir(old_cwd)
        try:
            os.unlink(ass_path)
        except Exception:
            pass

    progress_cb(100, f"Story video complete: {os.path.basename(args.output)}")

    story_title = _generate_catchy_title(story_text, prompt) or f"Real Story | {prompt[:60].title()}"
    story_description = _generate_description(story_text, story_title)

    # Rename to use the story title for the filename
    def _safe_name(title, suffix=".mp4", max_len=100):
        uid = uuid.uuid4().hex[:8]
        safe = "".join(c if c.isalnum() or c in " _-" else "_" for c in title).strip()
        safe = safe[:max_len].rstrip("._- ")
        return (safe or "story") + f"_{uid}" + suffix

    titled_path = os.path.join(os.path.dirname(args.output),
                               _safe_name(story_title))
    if titled_path != args.output and not os.path.exists(titled_path):
        try:
            os.rename(args.output, titled_path)
            args.output = titled_path
        except Exception:
            pass

    _save_meta(args.output, story_title, story_description, story_text)

    return {
        "path": args.output,
        "title": story_title,
        "description": story_description,
        "story_text": story_text,
    }
