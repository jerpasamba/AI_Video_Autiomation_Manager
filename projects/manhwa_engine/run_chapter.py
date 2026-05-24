"""
Universal chapter pipeline: run_chapter.py <N>
  python run_chapter.py 2     # Run all steps for chapter 2
  python run_chapter.py 2 --panels-only  # Only regenerate bad panels
  python run_chapter.py 2 --video-only   # Only re-render video
  python run_chapter.py 2 --meta-only    # Only generate YouTube metadata
"""
import sys, json, os, logging
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "final"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


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


def run_chapter(chapter_num, flags=None):
    if flags is None:
        flags = set()

    CHAPTER = chapter_num
    OUT = ROOT / "output" / "Final" / f"ch{CHAPTER:02d}"
    os.makedirs(OUT / "panels", exist_ok=True)

    script_path = OUT / "script.json"
    audio_path = OUT / "voice.mp3"
    panel_video = OUT / "panel_video.mp4"
    output_video = OUT / f"chapter_{CHAPTER:02d}_video.mp4"

    # STEP 1: Generate chapter script
    if "script" in flags or not flags:
        if not script_path.exists() or "script" in flags:
            from generate_chapter import generate_chapter
            step("Generating chapter script", generate_chapter,
                 CHAPTER, output_path=str(script_path), use_gemini=False)

    with open(script_path, encoding="utf-8") as f:
        script = json.load(f)
    total_panels = sum(len(s["panels"]) for s in script["scenes"])
    log.info("Script: %s (%d scenes, %d panels)", script["title"], len(script["scenes"]), total_panels)

    # STEP 2: Generate panel images
    if "panels" in flags or not flags:
        from generate_panels import generate_all_panels
        step("Generating panel images", generate_all_panels,
             script, output_dir=str(OUT / "panels"))

    # Rebuild panel map
    panel_map = {}
    for scene in script["scenes"]:
        snum = scene["scene_num"]
        for panel in scene["panels"]:
            pnum = panel["panel_num"]
            fname = f"s{snum:02d}_p{pnum:02d}.png"
            fpath = OUT / "panels" / fname
            if fpath.exists():
                panel_map[f"{snum}_{pnum}"] = str(fpath)

    # STEP 3: Generate voice
    if "voice" in flags or not flags:
        from generate_voice import generate_voice
        step("Generating voice", generate_voice, script, output_path=str(audio_path))

    audio_duration = 30.0
    if audio_path.exists():
        try:
            from moviepy import AudioFileClip
            ac = AudioFileClip(str(audio_path))
            audio_duration = ac.duration
            ac.close()
        except Exception:
            pass

    # STEP 4: Sync bubbles
    if "subs" in flags or not flags:
        from sync_bubbles import sync_bubbles
        step("Syncing bubbles", sync_bubbles, script, str(audio_path))

    # STEP 5: Create panel video
    if "video" in flags or not flags:
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
        from camera_motion import create_panel_video
        step("Creating panel video", create_panel_video,
             all_paths, all_infos, str(panel_video), audio_duration)

    # STEP 6: Render final video
    if "render" in flags or not flags:
        if panel_video.exists() and audio_path.exists():
            from render_comic import render_comic
            result = step("Rendering final video", render_comic,
                          str(panel_video), str(audio_path), output_path=str(output_video))

    # STEP 7: Generate YouTube metadata
    if "meta" in flags or not flags:
        try:
            from generate_youtube_meta import generate_youtube_meta
            step("Generating YouTube metadata", generate_youtube_meta,
                 script, OUT, CHAPTER, audio_duration)
        except Exception as e:
            log.warning("YouTube metadata skipped: %s", e)

    # STEP 8: Generate YouTube thumbnail
    if "thumb" in flags or not flags:
        try:
            from generate_thumbnail import generate_thumbnail
            ch_title = script.get("title", f"Chapter {CHAPTER}")
            clean = ch_title.replace(f"Chapter {CHAPTER}: ", "").replace(f"Chapter {CHAPTER}", "").strip()
            step("Generating YouTube thumbnail", generate_thumbnail,
                 CHAPTER, clean, script, OUT, OUT / "panels")
        except Exception as e:
            log.warning("Thumbnail skipped: %s", e)

    # Summary
    print("\n" + "=" * 60)
    print(f"  CHAPTER {CHAPTER} COMPLETE")
    print("=" * 60)
    if output_video.exists():
        print(f"  Video: {output_video}")
        size = os.path.getsize(output_video) / (1024 * 1024)
        print(f"  Size: {size:.1f} MB")
    else:
        print("  Video: not generated (use without --meta-only)")
    print(f"  Duration: {audio_duration:.1f}s ({audio_duration/60:.1f} min)")
    print(f"  Panels: {total_panels}")
    meta_path = OUT / "youtube_meta.json"
    if meta_path.exists():
        print(f"  YouTube metadata: {meta_path}")
    thumb_path = OUT / "thumbnail.jpg"
    if thumb_path.exists():
        print(f"  Thumbnail: {thumb_path}")
    print("=" * 60)

    return output_video


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run full chapter pipeline")
    parser.add_argument("chapter", type=int, help="Chapter number")
    parser.add_argument("--panels-only", action="store_true", help="Regenerate panels only")
    parser.add_argument("--video-only", action="store_true", help="Re-render video only")
    parser.add_argument("--meta-only", action="store_true", help="Generate YouTube metadata only")
    parser.add_argument("--thumb-only", action="store_true", help="Generate YouTube thumbnail only")
    parser.add_argument("--no-gemini", action="store_true", help="Skip Gemini for script generation")
    args = parser.parse_args()

    flags = set()
    if args.panels_only:
        flags = {"panels"}
    elif args.video_only:
        flags = {"video", "render"}
    elif args.meta_only:
        flags = {"meta"}
    elif args.thumb_only:
        flags = {"thumb"}
    else:
        flags = set()

    run_chapter(args.chapter, flags)
