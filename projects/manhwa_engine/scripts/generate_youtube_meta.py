import os
import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent.parent

def format_timestamp(seconds):
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m}:{s:02d}"

def generate_youtube_meta(script, output_dir, chapter_num, audio_duration=0):
    title_raw = script.get("title", f"Chapter {chapter_num}")
    ch_title = title_raw.replace(f"Chapter {chapter_num}: ", "").replace(f"Chapter {chapter_num}", "").strip()

    series = "The Star-Touched Boy"
    title = f"{series} | Chapter {chapter_num}: {ch_title} (Manhwa Motion Comic)"

    scenes = script.get("scenes", [])
    total_panels = sum(len(s.get("panels", [])) for s in scenes)

    desc_lines = [
        f"📖 {series}",
        f"🎬 Chapter {chapter_num}: {ch_title}",
        "",
        "A young boy with the soul of an ancient sage begins his second life in a peaceful village.",
        "But when you're the most powerful mage reincarnated... the slow life isn't always easy.",
        "",
        "✨ TIMESTAMPS:",
    ]

    if audio_duration > 0 and scenes:
        scenes_total = len(scenes)
        scene_duration = (audio_duration - 5.0) / max(scenes_total, 1)
        for i, scene in enumerate(scenes):
            ts = 5.0 + i * scene_duration
            loc = scene.get("location", f"Scene {i+1}")
            desc_lines.append(f"  {format_timestamp(ts)} - {loc}")

    desc_lines.extend([
        "",
        "🎨 This motion comic is generated using AI:",
        "  • Story & Panels: Custom AI pipeline",
        "  • Art: Pollinations.ai",
        "  • Voice: Edge-TTS",
        "  • Video: FFmpeg compositing",
        "",
        f"📊 Chapter Stats:",
        f"  • Scenes: {scenes_total}",
        f"  • Panels: {total_panels}",
        f"  • Duration: {format_timestamp(audio_duration)}" if audio_duration else "",
        "",
        "🔔 Subscribe for more chapters!",
        "",
        "#TheStarTouchedBoy #Manhwa #MotionComic #Webtoon #Fantasy #Anime",
        "#AIPipeline #Reincarnation #Magic #SliceOfLife",
    ])
    description = "\n".join(line for line in desc_lines if line)

    tags = [
        "The Star-Touched Boy", f"Chapter {chapter_num}", ch_title,
        "manhwa", "motion comic", "webtoon", "anime",
        "fantasy", "reincarnation", "magic", "isekai",
        "AI generated", "AI animation", "AI manhwa",
        "slice of life", "fantasy adventure",
        "anime style", "manga",
    ]

    comments = [
        {
            "author": "NoraFan99",
            "text": f"Nora charging in with her shield never gets old! 'Respect my authority!' 😂 Best girl energy!",
            "likes": 42
        },
        {
            "author": "OldSoulReader",
            "text": f"I love how Lian is this ancient wise sage but still gets dragged into kid adventures. The Moonpetal meadow scene was gorgeous!",
            "likes": 38
        },
        {
            "author": "WebtoonLover",
            "text": f"The Whisperwood Forest feels so alive! The pixies and the Night Bear — this chapter had such a good balance of wonder and tension.",
            "likes": 27
        },
        {
            "author": "MagicSystemNerd",
            "text": f"Starlight Weave is such a cool spell! Light/Lunar fusion magic — I love how Lian's old life knowledge combines with this world's unique system.",
            "likes": 21
        },
        {
            "author": "DailyReader",
            "text": f"Elder May is definitely more than she seems. That enchanted whistle is going to be important later, I can feel it.",
            "likes": 19
        },
    ]

    meta = {
        "title": title,
        "description": description,
        "tags": tags,
        "comments": comments,
        "filename_safe": f"chapter_{chapter_num:02d}_{ch_title.lower().replace(' ','_')}",
    }

    meta_path = Path(output_dir) / "youtube_meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    log.info("YouTube metadata saved: %s", meta_path)

    txt_path = Path(output_dir) / "youtube_description.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"TITLE:\n{title}\n\n")
        f.write(f"DESCRIPTION:\n{description}\n\n")
        f.write(f"TAGS:\n{', '.join(tags)}\n\n")
        f.write("SAMPLE COMMENTS:\n")
        for c in comments:
            f.write(f"  {c['author']} ({c['likes']} likes): {c['text']}\n")
    log.info("YouTube description text saved: %s", txt_path)

    print(f"\n{'='*60}")
    print(f"  YOUTUBE METADATA — Chapter {chapter_num}")
    print(f"{'='*60}")
    print(f"  Title: {title}")
    print(f"  Description: {len(description)} chars")
    print(f"  Tags: {len(tags)}")
    print(f"  Comments: {len(comments)}")
    print(f"{'='*60}\n")

    return meta


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    import sys
    ch = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    out = ROOT / "output" / "Final" / f"ch{ch:02d}"
    script_path = out / "script.json"
    if script_path.exists():
        with open(script_path, encoding="utf-8") as f:
            script = json.load(f)
        audio_path = out / "voice.mp3"
        duration = 0
        if audio_path.exists():
            try:
                from moviepy import AudioFileClip
                ac = AudioFileClip(str(audio_path))
                duration = ac.duration
                ac.close()
            except Exception:
                pass
        generate_youtube_meta(script, out, ch, duration)
    else:
        log.error("Script not found: %s", script_path)
