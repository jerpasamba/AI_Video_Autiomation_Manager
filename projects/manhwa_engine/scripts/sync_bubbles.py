import os
import json
import logging
import re
from pathlib import Path

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent


def _group_words_into_segments(word_timing):
    if not word_timing:
        return []
    segments = []
    cur_words = []
    cur_start = None
    for wt in word_timing:
        t = wt["text"].strip()
        if not t:
            continue
        if cur_start is None:
            cur_start = wt["start"]
        cur_words.append(t)
        if t[-1] in (".", "!", "?", "\u201d", "\u201c"):
            segments.append({
                "start": cur_start,
                "end": wt["end"],
                "text": " ".join(cur_words),
            })
            cur_words = []
            cur_start = None
    if cur_words:
        segments.append({
            "start": cur_start,
            "end": word_timing[-1]["end"],
            "text": " ".join(cur_words),
        })
    return segments


def generate_subtitles(audio_path, output_path=None, script=None):
    if output_path is None:
        output_path = Path(audio_path).parent / "subtitles.srt"
    else:
        output_path = Path(output_path)
    os.makedirs(output_path.parent, exist_ok=True)

    timing_path = Path(audio_path).with_suffix(".timing.json")
    if timing_path.exists():
        try:
            with open(timing_path, encoding="utf-8") as f:
                word_timing = json.load(f)
            segments = _group_words_into_segments(word_timing)
            if segments:
                with open(output_path, "w", encoding="utf-8") as f:
                    for i, seg in enumerate(segments):
                        f.write(f"{i + 1}\n")
                        f.write(f"{_format_time(seg['start'])} --> {_format_time(seg['end'])}\n")
                        f.write(f"{seg['text']}\n\n")
                log.info("Word-timing subtitles saved: %s (%d segments)", output_path.name, len(segments))
                return segments, str(output_path)
        except Exception as e:
            log.warning("Word timing failed (%s), trying Whisper", e)

    try:
        import whisper
        log.info("Transcribing audio with Whisper...")
        model = whisper.load_model("base")
        result = model.transcribe(str(audio_path))
        segments = result.get("segments", [])

        with open(output_path, "w", encoding="utf-8") as f:
            for i, seg in enumerate(segments):
                start = seg["start"]
                end = seg["end"]
                text = re.sub(r'[\(\)\[\]]', '', seg["text"].strip())
                if not text:
                    continue
                f.write(f"{i + 1}\n")
                f.write(f"{_format_time(start)} --> {_format_time(end)}\n")
                f.write(f"{text}\n\n")

        log.info("Whisper subtitles saved: %s (%d segments)", output_path.name, len(segments))
        return segments, str(output_path)
    except ImportError:
        log.warning("Whisper not installed, creating fallback timing")
        return _create_fallback_timing(audio_path, output_path, script=script)
    except Exception as e:
        log.warning("Whisper failed (%s), creating fallback timing", e)
        return _create_fallback_timing(audio_path, output_path, script=script)


def _format_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _create_fallback_timing(audio_path, output_path, script=None):
    try:
        from moviepy import AudioFileClip
        clip = AudioFileClip(str(audio_path))
        duration = clip.duration
        clip.close()
    except Exception:
        duration = 30.0

    dialogue_texts = []
    if script:
        for scene in script.get("scenes", []):
            for n in scene.get("narration", []):
                dialogue_texts.append(n)
            for panel in scene.get("panels", []):
                d = panel.get("dialogue")
                if d and d.get("text"):
                    dialogue_texts.append(d["text"])
                thought = panel.get("thought")
                if thought:
                    dialogue_texts.append(thought)

    if not dialogue_texts:
        dialogue_texts = ["Part 1", "Part 2", "Part 3"]

    segments = []
    num_segments = len(dialogue_texts)
    if num_segments <= 1:
        segments = [{"start": 0.0, "end": duration, "text": dialogue_texts[0]}]
    else:
        chunk = duration / num_segments
        for i, text in enumerate(dialogue_texts):
            text_clean = re.sub(r'[\(\)\[\]]', '', text).strip()
            segments.append({
                "start": i * chunk,
                "end": min((i + 1) * chunk, duration),
                "text": text_clean,
            })

    with open(output_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segments):
            f.write(f"{i + 1}\n")
            f.write(f"{_format_time(seg['start'])} --> {_format_time(seg['end'])}\n")
            f.write(f"{seg['text']}\n\n")

    log.info("Fallback subtitles saved: %s (%d segments)", output_path, len(segments))
    return segments, str(output_path)


def map_bubbles_to_timing(script, segments):
    dialogues = []
    scenes = script.get("scenes", [])
    for scene in scenes:
        for panel in scene.get("panels", []):
            dialogue = panel.get("dialogue")
            if dialogue:
                dialogues.append({
                    "scene_num": scene.get("scene_num", 1),
                    "panel_num": panel.get("panel_num", 1),
                    "speaker": dialogue.get("speaker", ""),
                    "text": dialogue.get("text", ""),
                })

    timed_bubbles = []
    total_dialogues = len(dialogues)
    total_segments = len(segments)

    if total_dialogues == 0:
        return timed_bubbles

    for i, d in enumerate(dialogues):
        seg_idx = min(i, total_segments - 1) if total_segments > 0 else 0
        if seg_idx >= 0:
            start = segments[seg_idx]["start"] if seg_idx < len(segments) else 0
            end = segments[seg_idx]["end"] if seg_idx < len(segments) else start + 3
        else:
            start = 0
            end = 3

        timed_bubbles.append({
            "scene_num": d["scene_num"],
            "panel_num": d["panel_num"],
            "text": d["text"],
            "speaker": d["speaker"],
            "start_time": round(start, 2),
            "end_time": round(end, 2),
        })

    return timed_bubbles


def sync_bubbles(script=None, audio_path=None, output_path=None):
    if script is None:
        script_path = ROOT / "output" / "Final" / "ch01" / "script.json"
        if script_path.exists():
            with open(script_path) as f:
                script = json.load(f)
        else:
            log.error("No script found")
            return [], None

    if audio_path is None:
        audio_path = ROOT / "output" / "Final" / "ch01" / "voice.mp3"

    if not os.path.exists(audio_path):
        log.warning("Audio not found at %s", audio_path)
        return [], None

    segments, subs_path = generate_subtitles(audio_path, output_path, script=script)
    timed_bubbles = map_bubbles_to_timing(script, segments)

    bubbles_path = Path(audio_path).parent / "bubble_timing.json"
    with open(bubbles_path, "w", encoding="utf-8") as f:
        json.dump(timed_bubbles, f, indent=2, ensure_ascii=False)

    log.info("Bubble timing saved: %s (%d bubbles)", bubbles_path, len(timed_bubbles))
    return timed_bubbles, str(subs_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    bubbles, subs = sync_bubbles()
    if bubbles:
        print("Bubbles synced:", len(bubbles))
        print("Subtitles:", subs)
