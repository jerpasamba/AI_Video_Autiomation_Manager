import sys, json, os, logging
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "final"))

CHAPTER = 2
OUT = ROOT / "output" / "Final" / f"ch{CHAPTER:02d}"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)
os.makedirs(OUT / "panels", exist_ok=True)

def step(name, func, *args, **kwargs):
    log.info("=" * 50)
    log.info("STEP: %s", name)
    log.info("=" * 50)
    try:
        r = func(*args, **kwargs)
        log.info("%s: OK", name)
        return r
    except Exception as e:
        log.error("%s FAILED: %s", name, e)
        raise

def main():
    # STEP 1: Generate chapter script
    script_path = OUT / "script.json"
    if not script_path.exists():
        from generate_chapter import generate_chapter
        generate_chapter(CHAPTER, output_path=str(script_path), use_gemini=False)

    with open(script_path) as f:
        script = json.load(f)
    total = sum(len(s["panels"]) for s in script["scenes"])
    log.info("Script: %s (%d scenes, %d panels)", script["title"], len(script["scenes"]), total)

    # STEP 2: Generate panel images
    from generate_panels import generate_all_panels
    panel_map = step("Generating panel images", generate_all_panels,
                     script, output_dir=str(OUT / "panels"))

    # STEP 3: Generate voice
    from generate_voice import generate_voice
    audio_path = step("Generating voice", generate_voice,
                      script, output_path=str(OUT / "voice.mp3"))

    audio_duration = 30.0
    if audio_path and os.path.exists(audio_path):
        try:
            from moviepy import AudioFileClip
            ac = AudioFileClip(str(audio_path))
            audio_duration = ac.duration
            ac.close()
        except Exception:
            pass

    # STEP 4: Sync bubbles
    from sync_bubbles import sync_bubbles
    step("Syncing bubbles", sync_bubbles, script, audio_path)

    # STEP 5: Build flat panel list and create simple panel video
    from camera_motion import create_panel_video

    all_paths = []
    all_infos = []
    for scene in script["scenes"]:
        snum = scene["scene_num"]
        for panel in scene["panels"]:
            pnum = panel["panel_num"]
            key = f"{snum}_{pnum}"
            pp = panel_map.get(key)
            if pp and os.path.exists(pp):
                all_paths.append(pp)
                all_infos.append(panel)

    log.info("Panels for video: %d, audio: %.1fs", len(all_paths), audio_duration)
    panel_video = str(OUT / "panel_video.mp4")
    step("Creating panel video", create_panel_video,
         all_paths, all_infos, panel_video, audio_duration)

    # STEP 6: Render final video (title + panels + audio + subs)
    from render_comic import render_comic
    output = str(OUT / f"chapter_{CHAPTER:02d}_video.mp4")
    result = step("Rendering final video", render_comic,
                  panel_video, audio_path, output_path=output)

    print("\n" + "=" * 60)
    print("  CHAPTER %d COMPLETE" % CHAPTER)
    print("=" * 60)
    if result and os.path.exists(result):
        print("  Video: %s" % result)
        print("  Size: %.1f MB" % (os.path.getsize(result) / (1024 * 1024)))
        print("  Duration: %.1fs" % audio_duration)
    else:
        print("  Video generation had issues")
    print("=" * 60)


if __name__ == "__main__":
    main()
