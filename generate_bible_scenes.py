"""
Generate full scenes/panels for all summary-only chapters (10-99) using Gemini,
writes them directly into story_bible.json so chapters are as rich as 1-8.
Run once: python generate_bible_scenes.py
"""
import os
import json
import re
import time
import logging
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("generate_bible_scenes")

BIBLE_PATH = Path("projects/manhwa_engine/story_bible.json")


def load_bible():
    with open(BIBLE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_bible(bible):
    with open(BIBLE_PATH, "w", encoding="utf-8") as f:
        json.dump(bible, f, indent=2, ensure_ascii=False)


def build_character_descriptions(bible):
    chars = bible.get("characters", {})
    lines = []

    prot = chars.get("protagonist", {})
    lines.append(f"PROTAGONIST: {prot.get('name', 'MC')}")
    lines.append(f"Appearance: {prot.get('appearance', '')}")
    lines.append(f"Personality: {prot.get('personality', '')}")
    lines.append(f"Current power level: {prot.get('initial_rank', '')}")
    lines.append("")

    for role_key in ("family", "supporting"):
        for c in chars.get(role_key, []):
            lines.append(f"{role_key.upper()}: {c.get('name', '')} ({c.get('role', '')})")
            lines.append(f"Appearance: {c.get('appearance', '')}")
            if c.get("personality"):
                lines.append(f"Personality: {c.get('personality', '')}")
            lines.append("")

    return "\n".join(lines)


def build_system_ui_desc(bible):
    system = bible.get("characters", {}).get("system_ui", {})
    elements = system.get("elements", [])
    if not elements:
        return ""
    lines = ["SYSTEM UI DESIGN:"]
    for e in elements:
        lines.append(f"- {e}")
    colors = system.get("colors", {})
    if colors:
        lines.append("\nCOLOR PALETTE:")
        for k, v in colors.items():
            lines.append(f"  {k}: RGB{tuple(v)}")
    return "\n".join(lines)


def build_prompt(bible, chapter):
    prot = bible.get("characters", {}).get("protagonist", {})
    world = bible.get("world", {})
    char_desc = build_character_descriptions(bible)
    system_desc = build_system_ui_desc(bible)
    narrator_voice = prot.get("narration_voice", "Warm, playful, with gentle humor")
    chapter_json = json.dumps(chapter, indent=2, ensure_ascii=False)

    return f"""You are a Korean manhwa (webtoon) writer. Create detailed scene-by-scene panels for Chapter {chapter['number']} of the manhwa '{bible['title']}'.

WORLD SETTING:
{world.get('setting', '')}
{world.get('rules', '')}

CHARACTER DESCRIPTIONS (maintain these EXACTLY for visual consistency):
{char_desc}
{system_desc}

POWERS GROWTH PATH:
{json.dumps(prot.get('powers_growth', []), indent=2)}

PROTAGONIST'S INTERNAL NARRATION VOICE:
{narrator_voice}

KOREAN WEBTOON STYLE REQUIREMENTS:
- Korean manhwa/webtoon style: full color, cel-shaded with soft gradients, natural color palette
- At least 60% of panels should NOT show the MC's face — vary perspectives constantly
- Use thought bubbles / dark narration boxes for internal monologue (Korean webtoon style)
- Every scene needs at least 2 panels with internal narration
- Slow pacing — let scenes breathe with environment shots and detail shots between action
- Poetic, warm internal narration style for the protagonist
- System notifications appear as floating translucent golden panels with warm light

HERE IS THE CHAPTER OUTLINE TO EXPAND:
{chapter_json}

Based on this outline, create 4-8 scenes, each with 5-9 panels (40-70 panels total).

Each panel needs:
- "panel_num": sequential number within scene
- "type": one of 16 types — "abstract_establishing", "environment", "detail_environment", "ui_focus", "object_detail", "hands_only", "character_focus", "reaction", "silhouette", "thought_focus", "action", "impact_freeze", "pov_action", "low_angle_threat", "aftermath", "scale_shot"
- "composition": detailed visual description — MUST include lighting, colors, camera angle, mood
- "characters": list of characters present (empty array [] if no characters)
- "dialogue": {{"speaker": "Name", "text": "spoken words", "dialogue_type": "default"}} or null
- "thought": INTERNAL MONOLOGUE narration text (Korean webtoon style dark box) or null

DIALOGUE TYPES:
- "default": normal speech bubble
- "whisper": quiet or whispered dialogue
- "sfx": sound effect or yell
- "system": mana system / magic interface text (golden glow)
- "yell": loud shouting

Shot diversity rules:
- NEVER repeat the same shot type twice in a row
- Alternate: wide -> detail -> character -> abstract -> wide
- Every 3rd panel should be a "breathing panel" — no dialogue, pure visual atmosphere

CRITICAL: Return ONLY valid JSON. No markdown, no explanations.
The JSON structure:
{{
  "scenes": [
    {{
      "scene_num": 1,
      "location": "Location Name - TimeOfDay",
      "mood": "comma,separated,keywords",
      "narration": ["Narration line 1", "Narration line 2"],
      "panels": [
        {{
          "panel_num": 1,
          "type": "establishing",
          "composition": "visual description including lighting, colors, camera angle, mood",
          "characters": [],
          "dialogue": null,
          "thought": "Internal monologue in dark Korean webtoon narration box"
        }}
      ]
    }}
  ]
}}"""


def call_gemini(prompt_text):
    api_keys = os.getenv("GEMINI_API_KEYS", "")
    keys = [k.strip() for k in api_keys.split(",") if k.strip()]
    if not keys:
        log.error("No GEMINI_API_KEYS found in .env")
        return None

    from google import genai
    from google.genai import types

    last_error = None
    for key in keys:
        try:
            client = genai.Client(api_key=key)
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt_text,
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    max_output_tokens=32768,
                ),
            )
            return response.text
        except Exception as e:
            last_error = e
            log.warning("Gemini key failed: %s", e)
            continue
    raise last_error if last_error else Exception("No API keys available")


def parse_response(text):
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if json_match:
        text = json_match.group(1)
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r'^```[a-z]*\n?', '', text)
        text = re.sub(r'\n?```$', '', text)
    return json.loads(text)


def scenes_match_bible_format(chapter_num, scenes):
    """Validate scenes have the required fields."""
    if not scenes:
        return False
    for s in scenes:
        if not isinstance(s, dict):
            return False
        if "location" not in s or "mood" not in s:
            return False
        if "panels" not in s or not isinstance(s["panels"], list) or len(s["panels"]) < 3:
            return False
        for p in s["panels"]:
            if "type" not in p or "composition" not in p:
                return False
    return True


def merge_with_bible(bible_chapter, generated_script):
    """Merge generated scenes into bible chapter format."""
    from pprint import pformat

    scenes = generated_script.get("scenes", [])
    merged = []
    for i, s in enumerate(scenes):
        merged.append({
            "id": s.get("id", f"{bible_chapter['number']}.{i+1}"),
            "scene_num": i + 1,
            "location": s.get("location", ""),
            "mood": s.get("mood", ""),
            "narration": s.get("narration", []),
            "panels": [
                {
                    "num": p.get("panel_num", j + 1),
                    "type": p.get("type", "default"),
                    "composition": p.get("composition", ""),
                    "characters": [c.strip() for c in (p.get("characters") or []) if c.strip()],
                    "dialogue": p.get("dialogue", None),
                    "thought": p.get("thought", None),
                }
                for j, p in enumerate(s.get("panels", []))
            ],
        })
    bible_chapter["scenes"] = merged
    return bible_chapter


def main():
    bible = load_bible()
    chapters = bible.get("chapters", [])
    total = len(chapters)
    summary_only = [c for c in chapters if not c.get("scenes") and c["number"] >= 10]
    log.info("Found %d chapters total, %d summary-only chapters to process (10+)", total, len(summary_only))

    for i, chapter in enumerate(summary_only):
        ch_num = chapter["number"]
        ch_title = chapter.get("title", "")

        checkpoint_file = Path(f"output/trial/ch{ch_num:02d}_generated.json")
        if checkpoint_file.exists():
            log.info("Ch%d already has checkpoint, loading...", ch_num)
            with open(checkpoint_file, encoding="utf-8") as f:
                saved = json.load(f)
            scenes = saved.get("scenes", [])
        else:
            log.info("[%d/%d] Generating scenes for Ch%d: %s...", i + 1, len(summary_only), ch_num, ch_title)
            prompt = build_prompt(bible, chapter)
            try:
                text = call_gemini(prompt)
                if not text:
                    log.warning("No response for Ch%d, skipping", ch_num)
                    continue
                parsed = parse_response(text)
                scenes = parsed.get("scenes", [])
            except Exception as e:
                log.error("Failed to generate Ch%d: %s", ch_num, e)
                continue

            if not scenes_match_bible_format(ch_num, scenes):
                log.warning("Ch%d generated invalid scenes, skipping", ch_num)
                continue

            os.makedirs("output/trial", exist_ok=True)
            with open(checkpoint_file, "w", encoding="utf-8") as f:
                json.dump({"scenes": scenes}, f, indent=2, ensure_ascii=False)
            log.info("Ch%d: %d scenes, %d total panels", ch_num, len(scenes), sum(len(s["panels"]) for s in scenes))

        merge_with_bible(chapter, {"scenes": scenes})
        save_bible(bible)
        log.info("Ch%d saved to bible (%d scenes, %d panels)", ch_num, len(scenes), sum(len(s["panels"]) for s in scenes))

        if i < len(summary_only) - 1:
            delay = 3
            log.info("Waiting %ds before next chapter...", delay)
            time.sleep(delay)

    log.info("Done! All chapters processed and saved to bible.")


if __name__ == "__main__":
    main()
