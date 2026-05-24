import os
import json
import logging
import re
import copy
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
BIBLE_PATH = ROOT / "story_bible.json"


def load_bible():
    with open(BIBLE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_chapter_outline(bible, chapter_num):
    for ch in bible.get("chapters", []):
        if ch["number"] == chapter_num:
            return ch
    return None


def build_character_descriptions(bible):
    chars = bible.get("characters", {})
    lines = []

    prot = chars.get("protagonist", {})
    lines.append(f"PROTAGONIST: {prot.get('name', 'MC')}")
    lines.append(f"Appearance: {prot.get('appearance', '')}")
    lines.append(f"Personality: {prot.get('personality', '')}")
    lines.append(f"Current power level: {prot.get('initial_rank', '')}")
    lines.append("")

    family = chars.get("family", [])
    for f_member in family:
        lines.append(f"FAMILY: {f_member.get('name', '')} ({f_member.get('role', '')})")
        lines.append(f"Appearance: {f_member.get('appearance', '')}")
        lines.append("")

    supporting = chars.get("supporting", [])
    for s in supporting:
        lines.append(f"CHARACTER: {s.get('name', '')} ({s.get('role', '')})")
        lines.append(f"Appearance: {s.get('appearance', '')}")
        lines.append(f"Personality: {s.get('personality', '')}")
        lines.append("")

    return "\n".join(lines)


def build_system_ui_desc(bible):
    system = bible.get("characters", {}).get("system_ui", {})
    elements = "\n".join(f"- {e}" for e in system.get("elements", []))
    colors = system.get("colors", {})
    color_str = "\n".join(f"  {k}: RGB{tuple(v)}" for k, v in colors.items())
    return f"SYSTEM UI DESIGN:\n{elements}\n\nCOLOR PALETTE:\n{color_str}"


def build_chapter_prompt(bible, chapter):
    prot = bible.get("characters", {}).get("protagonist", {})
    world = bible.get("world", {})
    char_desc = build_character_descriptions(bible)
    system_desc = build_system_ui_desc(bible)

    narrator_voice = prot.get("narration_voice", "Wry, melancholic, poetic but grounded")

    chapter_outline = json.dumps(chapter, indent=2, ensure_ascii=False)

    prompt = f"""You are a Korean manhwa (webtoon) writer. Create detailed scene-by-scene panels for Chapter {chapter['number']} of the manhwa '{bible['title']}'.

WORLD SETTING:
{world.get('setting', '')}
{world.get('rules', '')}

CHARACTER DESCRIPTIONS (maintain these EXACTLY for visual consistency):
{char_desc}

SYSTEM UI (show these panels when the System appears):
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
- Poetic, melancholic internal narration style for the protagonist
- System notifications appear as floating translucent dark-purple panels with silver runic borders

HERE IS THE CHAPTER OUTLINE TO EXPAND:
{chapter_outline}

Based on this outline, expand each scene into detailed panels. Each chapter should have 40-70 panels total depending on the scene count.

Each panel needs:
- "panel_num": sequential number within scene
- "type": one of the following 16 types — "abstract_establishing", "environment", "detail_environment", "ui_focus", "object_detail", "hands_only", "character_focus", "reaction", "silhouette", "thought_focus", "action", "impact_freeze", "pov_action", "low_angle_threat", "aftermath", "scale_shot"
- "composition": detailed visual description of what to DRAW — MUST include lighting, colors, camera angle, mood
- "characters": list of characters present in panel (empty array [] if no characters should appear)
- "dialogue": {{"speaker": "Name", "text": "spoken words", "dialogue_type": "default"}} or null
- "thought": INTERNAL MONOLOGUE narration text (Korean webtoon style dark box) or null

DIALOGUE TYPES:
- "default": normal speech bubble
- "whisper": quiet internal or whispered dialogue
- "sfx": sound effect or yell
- "system": Void Echo System text (purple-silver glow)
- "yell": loud shouting

Shot diversity rules:
- NEVER repeat the same shot type twice in a row
- Alternate: wide → detail → character → abstract → wide
- Every 3rd panel should be a "breathing panel" — no dialogue, pure visual atmosphere

CRITICAL: Return ONLY valid JSON. No markdown, no explanations.
The JSON structure:
{{
  "title": "Chapter {chapter['number']}: {chapter['title']}",
  "scenes": [
    {{
      "scene_num": 1,
      "location": "...",
      "mood": "mood_keywords",
      "narration": ["line1", "line2"],
      "panels": [
        {{
          "panel_num": 1,
          "type": "abstract_establishing",
          "composition": "visual description including lighting, colors, camera angle, mood",
          "characters": [],
          "dialogue": null,
          "thought": "Internal monologue in dark Korean webtoon narration box"
        }}
      ]
    }}
  ]
}}"""

    return prompt


def call_gemini(prompt_text, api_keys):
    from google import genai
    from google.genai import types

    keys = [k.strip() for k in api_keys.split(",") if k.strip()]
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
    raise last_error


def parse_response(text):
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if json_match:
        text = json_match.group(1)
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r'^```[a-z]*\n?', '', text)
        text = re.sub(r'\n?```$', '', text)
    return json.loads(text)


def merge_with_outline(bible_chapter, generated_script):
    scenes_with_bible = bible_chapter.get("scenes", [])
    gen_scenes = generated_script.get("scenes", [])

    merged_scenes = []
    for i, bible_scene in enumerate(scenes_with_bible):
        gen_scene = gen_scenes[i] if i < len(gen_scenes) else {}
        merged = {
            "id": bible_scene.get("id", f"{bible_chapter['number']}.{i+1}"),
            "scene_num": i + 1,
            "location": bible_scene.get("location", gen_scene.get("location", "")),
            "mood": bible_scene.get("mood", gen_scene.get("mood", "")),
            "narration": bible_scene.get("narration", gen_scene.get("narration", [])),
            "panels": [],
        }

        bible_panels = bible_scene.get("panels", [])
        gen_panels = gen_scene.get("panels", [])

        for j, bp in enumerate(bible_panels):
            gp = gen_panels[j] if j < len(gen_panels) else {}
            merged["panels"].append({
                "panel_num": bp.get("num", j + 1),
                "type": bp.get("type", gp.get("type", "default")),
                "composition": gp.get("composition", bp.get("composition", "")),
                "characters": bp.get("characters", gp.get("characters", [])),
                "dialogue": bp.get("dialogue", gp.get("dialogue", None)),
                "thought": bp.get("thought", gp.get("thought", None)),
            })

        merged_scenes.append(merged)

    return {
        "title": generated_script.get("title", bible_chapter.get("title", f"Chapter {bible_chapter['number']}")),
        "scenes": merged_scenes,
    }


def generate_chapter(chapter_num=1, output_path=None, use_gemini=True):
    bible = load_bible()
    chapter = get_chapter_outline(bible, chapter_num)

    if not chapter:
        log.error("Chapter %d not found in bible", chapter_num)
        return None

    if use_gemini:
        api_keys = os.getenv("GEMINI_API_KEYS", "")
        if api_keys:
            prompt = build_chapter_prompt(bible, chapter)
            log.info("Generating Chapter %d via Gemini (%d chars prompt)...",
                     chapter_num, len(prompt))
            try:
                raw = call_gemini(prompt, api_keys)
                generated = parse_response(raw)
                log.info("Gemini response received")
                script = merge_with_outline(chapter, generated)
            except Exception as e:
                log.warning("Gemini generation failed (%s), using bible outline", e)
                script = _bible_to_script(bible, chapter)
        else:
            log.info("No Gemini keys, using bible outline directly")
            script = _bible_to_script(bible, chapter)
    else:
        script = _bible_to_script(bible, chapter)

    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(script, f, indent=2, ensure_ascii=False)
        log.info("Saved Chapter %d script: %s", chapter_num, output_path)

    return script


def _bible_to_script(bible, chapter):
    scenes = []
    for s in chapter.get("scenes", []):
        panels = []
        for p in s.get("panels", []):
            panels.append({
                "panel_num": p.get("num", len(panels) + 1),
                "type": p.get("type", "default"),
                "composition": p.get("composition", ""),
                "characters": p.get("characters", []),
                "dialogue": p.get("dialogue", None),
                "thought": p.get("thought", None),
            })
        scenes.append({
            "id": s.get("id", f"{chapter['number']}.{len(scenes)+1}"),
            "scene_num": len(scenes) + 1,
            "location": s.get("location", ""),
            "mood": s.get("mood", ""),
            "narration": s.get("narration", []),
            "panels": panels,
        })

    return {
        "title": f"Chapter {chapter['number']}: {chapter['title']}",
        "scenes": scenes,
    }


def list_chapters():
    bible = load_bible()
    print(f"\nStory: {bible['title']}")
    print(f"World: {bible.get('world', {}).get('setting', '')[:80]}...\n")
    print("Characters:")
    prot = bible.get('characters', {}).get('protagonist', {})
    print(f"  MC: {prot.get('name', '')} ({prot.get('initial_rank', '')})")
    for f in bible.get('characters', {}).get('family', []):
        print(f"  Family: {f.get('name', '')} ({f.get('role', '')})")
    for s in bible.get('characters', {}).get('supporting', []):
        print(f"  Supporting: {s.get('name', '')} ({s.get('role', '')})")
    print("\nChapters:")
    for ch in bible.get("chapters", []):
        print(f"  Ch {ch['number']}: {ch['title']} (~{ch.get('estimated_duration_minutes', '?')}min) - {ch.get('summary', '')[:100]}...")
    print()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--chapter", type=int, default=1, help="Chapter number to generate")
    parser.add_argument("--list", action="store_true", help="List all chapters and exit")
    parser.add_argument("--no-gemini", action="store_true", help="Skip Gemini, use bible directly")
    parser.add_argument("--output", type=str, help="Output path for chapter script")
    args = parser.parse_args()

    if args.list:
        list_chapters()
    else:
        out = args.output or str(ROOT / "output" / "trial" / "chapter_script.json")
        script = generate_chapter(args.chapter, output_path=out, use_gemini=not args.no_gemini)
        if script:
            print(json.dumps(script, indent=2, ensure_ascii=False)[:2000])
            print(f"\n... ({len(json.dumps(script))} total chars)")
