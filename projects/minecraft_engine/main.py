import os
import sys
import json
import asyncio
import subprocess
import tempfile
import random
import urllib.request
import urllib.parse
from pathlib import Path
from app.subprocess_utils import get_ffmpeg_cmd, no_console_kwargs


def ffmpeg(args, **kwargs):
    cmd = [get_ffmpeg_cmd(), "-y"] + args
    kwargs = {**no_console_kwargs(), **kwargs}
    subprocess.run(cmd, check=True, **kwargs)



def ffprobe(path):
    try:
        import cv2
        cap = cv2.VideoCapture(path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        cap.release()
        if fps and fps > 0 and frames and frames > 0:
            return float(frames / fps)
    except Exception:
        pass
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", path],
            capture_output=True, text=True, **no_console_kwargs()
        )
        return float(r.stdout.strip())
    except Exception:
        return 60.0


def _ts_to_sec(ts):
    """Convert SRT timestamp (HH:MM:SS,mmm or HH:MM:SS.mmm) to seconds."""
    ts = ts.strip().replace(",", ".")
    parts = ts.split(":")
    return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])


def _sec_to_ass(sec):
    """Convert seconds to ASS timestamp H:MM:SS.mm."""
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _parse_srt_entries(srt_content):
    """Parse SRT content into list of (start_sec, end_sec, word) tuples."""
    entries = []
    for block in srt_content.strip().split("\n\n"):
        block = block.strip()
        if not block:
            continue
        parts = block.split("\n")
        time_line = None
        text_lines = []
        for p in parts:
            if "-->" in p:
                time_line = p
            elif not p.strip().isdigit():
                text_lines.append(p.strip())
        if not time_line or not text_lines:
            continue
        start_str, end_str = time_line.split("-->")
        start = _ts_to_sec(start_str)
        end = _ts_to_sec(end_str)
        word = "".join(text_lines).strip()
        if word:
            entries.append((start, end, word))
    return entries


def _group_words(entries):
    """Group word-level SRT entries into readable phrase-level subtitle groups.

    Uses timing gaps (>0.7s between words) to detect sentence boundaries,
    and limits groups to 5 words max for readability.
    Each group lasts at least 1.5s so text doesn't flash by.
    """
    if not entries:
        return []

    MAX_WORDS = 5
    GAP_THRESHOLD = 0.7

    groups = []
    current_words = []
    group_start = entries[0][0]
    prev_end = entries[0][1]

    for i, (start, end, word) in enumerate(entries):
        gap = start - prev_end
        # Start new group on: gap > threshold, or word limit reached
        if current_words and (gap > GAP_THRESHOLD or len(current_words) >= MAX_WORDS):
            group_end = max(prev_end, group_start + 1.5)
            groups.append((" ".join(current_words), group_start, group_end))
            current_words = []
            group_start = start

        current_words.append(word)
        prev_end = end

    if current_words:
        last_end = entries[-1][1]
        group_end = max(last_end, group_start + 1.5)
        groups.append((" ".join(current_words), group_start, group_end))

    # Merge very short groups (1-2 words) into the previous group
    merged = []
    for text, start, end in groups:
        word_count = len(text.split())
        if merged and word_count <= 2:
            prev_text, prev_start, prev_end = merged[-1]
            merged[-1] = (prev_text + " " + text, prev_start, end)
        else:
            merged.append((text, start, end))

    return merged


def srt_to_ass(srt_content):
    """Convert SRT to ASS with center-screen, large-subtitle styling.

    - Bold 72px font for maximum readability on mobile
    - Middle-centre alignment (text sits in the exact middle of the screen)
    - Strong black outline + subtle shadow so text is always legible
      without needing a background box
    - Words are grouped into readable phrases (4-5 words per line)
    - 60px horizontal padding so text stays within safe area
    """
    style = (
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\r\n"
        "Style: Default,Arial,72,&H00FFFFFF,&H00FFFFFF,&H00000000,"
        "&H00000000,-1,0,0,0,100,100,1.5,0,1,4,2,5,60,60,0,1\r\n"
    )
    lines = [
        "[Script Info]",
        "; ASS subtitle file (converted from SRT)",
        "ScriptType: v4.00+",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "",
        "[V4+ Styles]",
        style,
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    entries = _parse_srt_entries(srt_content)
    if not entries:
        return "\r\n".join(lines)

    if len(entries) > 3:
        groups = _group_words(entries)
    else:
        groups = [(" ".join(w for _, _, w in entries), entries[0][0], entries[-1][1])]

    for text, start_sec, end_sec in groups:
        start = _sec_to_ass(start_sec)
        end = _sec_to_ass(end_sec)
        text = text.replace("{", "\\{").replace("}", "\\}")
        lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")

    return "\r\n".join(lines)


def generate_story(prompt, system=None):
    """Generate a story using Pollinations AI."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": "openai",
        "messages": messages,
        "temperature": 1.0,
    }

    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        "https://text.pollinations.ai/openai",
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read())

    return result["choices"][0]["message"]["content"].strip()


async def generate_tts(text, voice, audio_path):
    import edge_tts

    communicate = edge_tts.Communicate(text, voice, boundary="WordBoundary")
    submaker = edge_tts.SubMaker()

    with open(audio_path, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                submaker.feed(chunk)

    return submaker


def build_ffmpeg(parkour_video, audio_path, ass_path, output_path, tts_duration):
    parkour_dur = ffprobe(parkour_video)
    loop_count = max(1, int(tts_duration / parkour_dur) + 1) if parkour_dur > 0 else 1

    print(f"  Parkour: {parkour_dur:.1f}s, looping ~{loop_count}x")
    print(f"  Audio: {tts_duration:.1f}s")

    ass_escaped = ass_path.replace("\\", "\\\\").replace(":", "\\:").replace("'", "'\\''")

    filter_complex = (
        f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
        f"crop=1080:1920,"
        f"subtitles='{ass_escaped}'[out]"
    )

    cmd = [
        "-stream_loop", str(loop_count - 1),
        "-i", parkour_video,
        "-i", audio_path,
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-map", "1:a",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-c:a", "aac",
        "-t", str(tts_duration),
        "-movflags", "+faststart",
        output_path,
    ]
    ffmpeg(cmd)
    return output_path


async def main_async(args):
    parkour = args.parkour_video
    output = args.output
    voice = args.voice

    if os.path.isdir(parkour):
        mp4s = [os.path.join(parkour, f) for f in os.listdir(parkour) if f.endswith(".mp4")]
        if not mp4s:
            print(f"No .mp4 files found in directory: {parkour}")
            return
        parkour = random.choice(mp4s)
        print(f"Picked random parkour: {os.path.basename(parkour)}")

    if not os.path.exists(parkour):
        print(f"Parkour video not found: {parkour}")
        print("Drop a Minecraft parkour .mp4 there and try again.")
        return

    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)

    if args.prompt:
        print(f"Generating story via Pollinations AI...")
        system = args.system or (
            "You are a storyteller for YouTube Shorts. Write a gripping, deeply realistic story "
            "(at least 500 words) about real-life relationship problems, emotional struggles, "
            "betrayal, heartbreak, family issues, or personal growth. "
            "Stories must feel 100%真实 — like something that actually happened to a real person. "
            "Use first-person POV, conversational tone, and raw emotion. "
            "Structure: open with a punchy hook, build tension, deliver a satisfying "
            "twist or emotional payoff, and end with a reflective closing line. "
            "Use vivid but believable details. Avoid fantasy, magic, superheroes, or supernatural elements. "
            "Vary sentence rhythm: mix very short impact sentences with slightly longer descriptive ones."
        )
        story = generate_story(args.prompt, system)
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        print(f"\n{'='*50}")
        print(story)
        print(f"{'='*50}\n")
    elif args.story:
        with open(args.story, "r", encoding="utf-8") as f:
            story = f.read().strip()
        if not story:
            print("Story file is empty.")
            return
    else:
        print("Provide --story <file> or --prompt <topic>")
        return

    print("Generating TTS audio + subtitles...")
    audio_path = output.replace(".mp4", "_tts.mp3")
    submaker = await generate_tts(story, voice, audio_path)

    srt_content = submaker.get_srt()
    if not srt_content.strip():
        print("No subtitles generated.")
        return

    ass_content = srt_to_ass(srt_content)
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
        tts_duration = 5

    entry_count = len([l for l in srt_content.split("\n") if "-->" in l])
    print(f"  {entry_count} subtitle entries, total {tts_duration:.1f}s")

    print("Compositing video...")
    try:
        build_ffmpeg(parkour, audio_path, ass_path, output, tts_duration)
        print(f"Done: {output}")
    finally:
        try:
            os.unlink(ass_path)
        except Exception:
            pass


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Minecraft Parkour Story Maker \u2014 turns a story into a shorts video"
    )
    src = parser.add_mutually_exclusive_group()
    src.add_argument("--story", help="Path to story text file")
    src.add_argument("--prompt", help="Generate story from topic using Pollinations AI")
    parser.add_argument("--system", help="System prompt for AI story generation")
    parser.add_argument("--bg", "--parkour-video", default="assets/parkour.mp4", dest="parkour_video",
                        help="Background video path or directory of parkour clips (default: assets/parkour.mp4)")
    parser.add_argument("--output", default="output/story_short.mp4",
                        help="Output video path")
    parser.add_argument("--voice", default="en-US-JennyNeural",
                        help="TTS voice (default: en-US-JennyNeural)")
    args = parser.parse_args()

    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
