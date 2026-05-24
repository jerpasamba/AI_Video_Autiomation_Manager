import os
import json
import logging
import asyncio
from pathlib import Path

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent


def get_narration_text(script):
    text_parts = []
    scenes = script.get("scenes", [])
    for scene in scenes:
        for nline in scene.get("narration", []):
            text_parts.append(nline)
        for panel in scene.get("panels", []):
            thought = panel.get("thought")
            if thought:
                text_parts.append(f'"{thought}"')
            dialogue = panel.get("dialogue")
            if dialogue:
                speaker = dialogue.get("speaker", "")
                text = dialogue.get("text", "")
                if speaker and speaker.lower() != "narrator":
                    text_parts.append(f'"{text}"')
                else:
                    text_parts.append(text)
    return " ".join(text_parts)


async def _generate_speech(text, output_path, voice="en-US-GuyNeural"):
    try:
        import edge_tts
        communicate = edge_tts.Communicate(text, voice)
        word_timing = []
        with open(output_path, "wb") as f:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
                elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
                    raw_text = chunk["text"]
                    offset_sec = chunk["offset"] / 10000000
                    duration_sec = chunk["duration"] / 10000000
                    if chunk["type"] == "SentenceBoundary":
                        words = raw_text.split()
                        if words:
                            per_word = duration_sec / len(words)
                            for i, w in enumerate(words):
                                ws = offset_sec + i * per_word
                                word_timing.append({
                                    "text": w,
                                    "start": round(ws, 3),
                                    "end": round(ws + per_word, 3),
                                })
                    else:
                        word_timing.append({
                            "text": raw_text,
                            "start": round(offset_sec, 3),
                            "end": round(offset_sec + duration_sec, 3),
                        })
        log.info("Voice saved: %s (%.1f KB)", os.path.basename(output_path), os.path.getsize(output_path) / 1024)

        timing_path = Path(output_path).with_suffix(".timing.json")
        with open(timing_path, "w", encoding="utf-8") as f:
            json.dump(word_timing, f, indent=2, ensure_ascii=False)
        log.info("Word timing saved: %s (%d words)", timing_path.name, len(word_timing))
        return True
    except Exception as e:
        log.error("Edge-TTS failed: %s", e)
        return False


def generate_voice(script=None, output_path=None, voice="en-US-GuyNeural"):
    if output_path is None:
        output_path = ROOT / "output" / "Final" / "ch01" / "voice.mp3"
    else:
        output_path = Path(output_path)
    os.makedirs(output_path.parent, exist_ok=True)

    if script is None:
        script_path = ROOT / "output" / "Final" / "ch01" / "script.json"
        if script_path.exists():
            with open(script_path) as f:
                script = json.load(f)
        else:
            log.warning("No script found, using fallback text")
            text = "This is a test narration for the manhwa motion comic."
            asyncio.run(_generate_speech(text, str(output_path), voice))
            return str(output_path)

    text = get_narration_text(script)
    if not text.strip():
        log.warning("Empty narration text")
        return None

    log.info("Generating voice (%.0f chars)...", len(text))
    success = asyncio.run(_generate_speech(text, str(output_path), voice))
    if success:
        return str(output_path)
    return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    result = generate_voice()
    if result:
        print("Voice saved:", result)
    else:
        print("Voice generation failed")
