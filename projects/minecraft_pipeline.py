import os
import sys
import asyncio
import random
import json

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


def get_generated_stories(config):
    path = _resolve_path(config)
    output_dir = os.path.join(path, "output")
    results = []
    if os.path.exists(output_dir):
        for fname in os.listdir(output_dir):
            if fname.endswith(".mp4"):
                fpath = os.path.join(output_dir, fname)
                results.append({
                    "path": fpath,
                    "title": fname.replace(".mp4", "").replace("_", " ").title(),
                    "size_mb": os.path.getsize(fpath) / (1024 * 1024),
                    "modified": os.path.getmtime(fpath),
                })
    return sorted(results, key=lambda x: x["modified"], reverse=True)


def generate_minecraft_story(prompt, progress_cb, config):
    _setup_imports(config)
    import main as mc_main

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
            existing = len(os.listdir(out_dir)) if os.path.exists(out_dir) else 0
            self.output = os.path.join(out_dir, f"story_{existing + 1}.mp4")
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

    return {
        "path": args.output,
        "title": os.path.basename(args.output),
    }
