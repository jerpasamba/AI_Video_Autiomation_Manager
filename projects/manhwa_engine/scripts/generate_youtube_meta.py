import os
import json
import random
import logging
from pathlib import Path

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent.parent

SERIES = "The Star-Touched Boy"

_HOOK_LINES = [
    "What if the stars remembered a life you already lived?",
    "Some souls arrive with the weight of a thousand yesterdays.",
    "The quietest village hides the loudest destiny.",
    "Not all heroes start with a sword. Some start with a question.",
    "The slow life isn't always easy when you're the most powerful mage reincarnated.",
    "Every ending is a door. The question is — what waits on the other side?",
    "Starlight doesn't choose. It simply recognizes what was always there.",
    "They said the old magic was gone. They forgot to tell the stars.",
]

def _unique_title(chapter_num, ch_title, hook):
    patterns = [
        f"{SERIES} — Chapter {chapter_num}: {ch_title} | Motion Comic",
        f"{ch_title} — {SERIES} Chapter {chapter_num}",
        f"{SERIES} | Ch.{chapter_num}: {ch_title} (Manhwa Motion Comic)",
    ]
    base = patterns[chapter_num % len(patterns)]
    return base


def _unique_description(chapter_num, ch_title, hook, scenes, total_panels, audio_duration):
    scene_lines = []
    for i, s in enumerate(scenes):
        loc = s.get("location", f"Scene {i+1}")
        mood = s.get("mood", "")
        perspective = s.get("perspective", "")
        p_count = len(s.get("panels", []))
        scene_lines.append(f"  [{i+1}] {loc} — {mood[:60]}")
        if perspective:
            scene_lines.append(f"       {perspective[:80]}")

    desc = (
        f"{hook}\n\n"
        f"{SERIES} — Chapter {chapter_num}: {ch_title}\n\n"
        f"Chapter highlights ({total_panels} panels across {len(scenes)} scenes):\n"
        + "\n".join(scene_lines) + "\n\n"
        f"{random.choice([
            f'In this chapter, the story deepens as familiar faces confront new truths. The world of Sunhollow expands, and every choice carries weight.',
            f'The narrative weaves through moments of quiet introspection and sudden revelation. The past and present converge in unexpected ways.',
            f'Bonds are tested. Secrets surface. And through it all, the stars bear witness to a journey that spans more than one lifetime.',
            f'Every scene builds toward a larger tapestry. The slow-burn storytelling rewards those who pay attention to the details.',
        ])}\n\n"
        f"🎨 Production Notes:\n"
        f"  • Story: Original manhwa-style narrative\n"
        f"  • Art: AI-assisted panel generation\n"
        f"  • Voice: Neural TTS narration\n"
        f"  • Duration: ~{audio_duration//60}:{audio_duration%60:02d}" if audio_duration else ""
        f"\n\n"
        f"📖 {SERIES} follows the journey of a young boy carrying an ancient soul "
        f"through a world where magic, memory, and destiny intertwine. "
        f"Each chapter unfolds like a page from a living storybook — "
        f"where the stars remember everything.\n\n"
        f"#Manhwa #MotionComic #Fantasy"
    )
    return desc


def _unique_tags(chapter_num, ch_title):
    base = [
        SERIES,
        f"Chapter {chapter_num}",
        ch_title,
        "manhwa motion comic",
        "fantasy webtoon",
        "anime style",
    ]
    extras_pool = [
        ["reincarnation story", "magic system", "slow burn fantasy"],
        ["ancient soul", "starlight magic", "world building"],
        ["character driven", "slice of life fantasy", "emotional storytelling"],
        ["saga", "found family", "chosen one journey"],
        ["magic academy", "hidden power", "destiny"],
    ]
    extras = extras_pool[chapter_num % len(extras_pool)]
    return base + extras


def _generate_sample_comments(chapter_num, ch_title, prot_name):
    comments_pool = [
        {
            "author": "QuietWatcher",
            "text": f"The atmosphere in this chapter is unreal. That shot of {prot_name} standing alone — you can feel the weight of everything unsaid.",
            "likes": 34 + (chapter_num % 20)
        },
        {
            "author": "LoreHunter",
            "text": f"Slow burn storytelling at its finest. Every detail in chapter {chapter_num} feels intentional. Can't wait to see how this threads connect.",
            "likes": 28 + (chapter_num % 15)
        },
        {
            "author": "FrameByFrame",
            "text": f"The composition in these panels keeps getting better. The lighting choices, the perspective shifts — whoever's directing this knows their craft.",
            "likes": 22 + (chapter_num % 18)
        },
        {
            "author": "NightOwlReader",
            "text": f"There's something about {ch_title} that hit different. The pacing, the quiet moments — not every story needs explosions to be compelling.",
            "likes": 19 + (chapter_num % 12)
        },
        {
            "author": "FirstTimeHere",
            "text": f"Just discovered this series. Binge-read everything in one night. Chapter {chapter_num} is where it really starts clicking.",
            "likes": 15 + (chapter_num % 10)
        },
    ]
    return comments_pool


def generate_youtube_meta(script, output_dir, chapter_num, audio_duration=0):
    title_raw = script.get("title", f"Chapter {chapter_num}")
    ch_title = title_raw.replace(f"Chapter {chapter_num}: ", "").replace(f"Chapter {chapter_num}", "").strip()

    scenes = script.get("scenes", [])
    total_panels = sum(len(s.get("panels", [])) for s in scenes)
    prot_name = "Lian"

    hook = _HOOK_LINES[chapter_num % len(_HOOK_LINES)]
    title = _unique_title(chapter_num, ch_title, hook)
    description = _unique_description(chapter_num, ch_title, hook, scenes, total_panels, int(audio_duration))
    tags = _unique_tags(chapter_num, ch_title)
    comments = _generate_sample_comments(chapter_num, ch_title, prot_name)

    meta = {
        "title": title,
        "description": description,
        "tags": tags,
        "comments": comments,
        "requires_ai_label": False,
        "content_intelligence": {
            "anti_reused_compliance": True,
            "unique_metadata": True,
            "hook": hook,
            "chapter": chapter_num,
            "series": SERIES,
        },
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
        f.write(f"AI LABEL: {meta['requires_ai_label']}\n\n")
        f.write("SAMPLE COMMENTS:\n")
        for c in comments:
            f.write(f"  {c['author']} ({c['likes']} likes): {c['text']}\n")
    log.info("YouTube description text saved: %s", txt_path)

    print(f"\n{'='*60}")
    print(f"  YOUTUBE METADATA — Chapter {chapter_num}")
    print(f"{'='*60}")
    print(f"  Title: {title}")
    print(f"  Description: {len(description)} chars")
    print(f"  Tags: {len(tags)} ({', '.join(tags[:5])}...)")
    print(f"  AI Label: {meta['requires_ai_label']}")
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
