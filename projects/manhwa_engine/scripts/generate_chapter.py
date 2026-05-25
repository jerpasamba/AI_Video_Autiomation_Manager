import os
import json
import logging
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


def generate_chapter(chapter_num=1, output_path=None, use_gemini=None):
    bible = load_bible()
    chapter = get_chapter_outline(bible, chapter_num)

    if not chapter:
        raise RuntimeError(
            f"Chapter {chapter_num} not found in story_bible.json. "
            f"Available chapters: {[c['number'] for c in bible.get('chapters', [])]}"
        )

    log.info("Generating Chapter %d from bible outline via Pollinations AI...", chapter_num)
    script = _bible_to_script(bible, chapter)

    if not script.get("scenes"):
        log.warning("Chapter %d has 0 scenes in bible - script NOT saved", chapter_num)
        raise RuntimeError(
            f"Chapter {chapter_num}: bible has 0 scenes."
        )

    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(script, f, indent=2, ensure_ascii=False)
        log.info("Saved Chapter %d script: %s", chapter_num, output_path)

    return script


def _bible_to_script(bible, chapter):
    ch_num = chapter["number"]
    title = chapter.get("title", "The Story Continues")
    scenes = []
    existing = chapter.get("scenes", [])
    if existing:
        for s in existing:
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
    else:
        summary = chapter.get("summary", "")
        import random
        import re
        random.seed(chapter["number"])
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', summary) if s.strip()]
        if len(sentences) < 3:
            sentences = [
                f"{chapter.get('title', 'The Story Continues')} begins.",
                summary[:150] or f"Chapter {chapter['number']} unfolds.",
                "The adventure takes an unexpected turn.",
                "Our heroes face new challenges and discoveries.",
            ]

        char_data = bible.get("characters", {})
        prot = char_data.get("protagonist", {}).get("name", "Lian")
        family = [f.get("name", "") for f in char_data.get("family", [])]
        supporting = [s.get("name", "") for s in char_data.get("supporting", [])]
        known_chars = [prot.lower()] + [c.lower() for c in family + supporting if c]

        world = bible.get("world", {})
        locations_pool = [
            world.get("key_locations", [])[i].get("name", f"Location_{i}")
            for i in range(min(10, len(world.get("key_locations", []))))
        ] or [
            "Sunhollow Village", "Whisperwood Forest", "Market Square",
            "Lian's Cottage", "Guild Hall", "Riverside",
            "Ancient Ruins", "Moonlit Meadow", "Training Grounds",
            "Elder May's Study"
        ]

        hook_templates = [
            f"What if the stars themselves remembered your name?",
            f"Some secrets don't stay buried — they grow roots.",
            f"The quietest moments often hide the loudest truths.",
            f"Not every hero starts with a sword. Some start with a question.",
            f"They said the old magic was gone. They were wrong.",
            f"Every ending is just a story waiting to begin again.",
            f"When the world falls silent, listen closer.",
            f"Strength isn't always measured in power. Sometimes, it's measured in letting go.",
        ]
        hook = hook_templates[ch_num % len(hook_templates)]

        num_scenes = random.choice([6, 7, 8])

        perspective_shifts = [
            f"(POV: {prot}'s eyes — intimate, close, every detail matters)",
            f"(POV: Omniscient — pulling back to reveal the larger world)",
            f"(POV: {random.choice(supporting or ['Nora'])} — an outsider's view)",
            f"(POV: Wide lens — the landscape itself becomes a character)",
            f"(POV: {prot}'s memory — a flashback tinted with emotion)",
            f"(POV: Cinematic — dramatic angles, shadows stretching long)",
            f"(POV: {random.choice(family or ['Elder May'])} — wisdom coloring every observation)",
        ]

        scene_configs = []
        for sn in range(1, num_scenes + 1):
            is_first = sn == 1
            is_last = sn == num_scenes

            if is_first:
                loc = locations_pool[0]
                mood = random.choice([
                    "bright with an undercurrent of mystery, hopeful yet cautious",
                    "intimate dawn light, secrets stirring beneath the surface",
                    "golden morning, the calm before something shifts",
                ])
                perspective = f"(HOOK: {hook})"
            elif is_last:
                loc = locations_pool[-1]
                mood = random.choice([
                    "twilight settling, reflection and resolve mingling",
                    "serene evening, threads of the story weaving together",
                    "quiet nightfall, the weight of what was learned",
                ])
                perspective = f"(CLOSING THOUGHT: Some stories write themselves. Others? You have to live them first.)"
            else:
                loc = locations_pool[(sn + ch_num) % len(locations_pool)]
                mood = random.choice([
                    "tense anticipation, the air thick with unspoken words",
                    "warm camaraderie, laughter cutting through the quiet",
                    "somber reflection, shadows of the past surfacing",
                    "electric energy, something ancient waking nearby",
                    "bittersweet nostalgia, memories coloring the present",
                    "raw vulnerability, masks slipping at last",
                ])
                perspective = perspective_shifts[(sn + ch_num) % len(perspective_shifts)]

            if sn <= len(sentences):
                seed = sentences[sn - 1]
            else:
                prev = sentences[(sn - 1) % len(sentences)]
                tension_words = ["unexpected", "bittersweet", "urgent", "mysterious", "tender", "fierce"]
                tw = tension_words[(sn + ch_num) % len(tension_words)]
                seed = f"{prev} Meanwhile, a {tw} turn of events shifts everything."

            scene_sentences = [seed]
            if len(sentences) > sn:
                scene_sentences.append(sentences[sn])
            elif is_first:
                scene_sentences.append(f"{title} doesn't start with a bang. It starts with a whisper.")
                scene_sentences.append("And whispers, as any old sage will tell you, carry the heaviest weight.")
            elif is_last:
                scene_sentences.append(f"As {title} draws to a close, the real question lingers — what comes next?")
                scene_sentences.append(f"{prot} stands at the threshold of something far greater than a single chapter.")
            else:
                deep_reflections = [
                    f"Here, at {loc}, the story breathes. Not every moment needs a monster. Some need a mirror.",
                    f"The world doesn't pause for heroes. It keeps turning, and they must turn with it.",
                    f"In the spaces between words, the truth often hides. Today, it refuses to stay silent.",
                    f"Trust is a fragile thing — built in heartbeats, shattered in seconds.",
                    f"The past doesn't stay in the past. It walks beside you, whether you invite it or not.",
                    f"Sometimes the bravest thing you can do is stop running. Turn around. Face it.",
                    f"Magic isn't about power. It's about connection — to the world, to each other, to yourself.",
                    f"Every choice ripples outward. Even the ones that seem small.",
                    f"Home isn't a place. It's the people who wait for you at the end of the road.",
                    f"The stars don't guide everyone. But for those they do, the journey is never accidental.",
                ]
                scene_sentences.append(deep_reflections[(sn + ch_num) % len(deep_reflections)])

            narration = [s for s in scene_sentences if s.strip()]
            panel_count = random.randint(8, 11)

            mentioned = [c for c in known_chars
                         if any(c in (s or "").lower() for s in scene_sentences)]
            if not mentioned:
                mentioned = [prot.lower()]

            panel_sequences = [
                ["environment", "character_focus", "action", "reaction", "thought_focus",
                 "detail_environment", "character_interaction", "reaction", "environment", "character_focus"],
                ["character_focus", "action", "reaction", "detail_environment", "character_interaction",
                 "thought_focus", "reaction", "action", "environment", "character_focus"],
                ["environment", "action", "character_focus", "reaction", "detail_environment",
                 "character_interaction", "thought_focus", "action", "reaction", "environment"],
            ]
            panel_seq = panel_sequences[(sn + ch_num) % len(panel_sequences)]

            comp_generators = [
                lambda loc, st: f"Wide cinematic establishing shot of {loc}. {st[:80]} Golden hour light filtering through, dust motes dancing. The kind of view that makes you forget to breathe.",
                lambda loc, st: f"Medium shot — characters occupy the frame with intent. {st[:80]} Lighting sculpts their features, shadows pooling where secrets hide.",
                lambda loc, st: f"Tight close-up. Micro-expressions carry the weight. {st[:60]} The camera lingers on the eyes — they always tell the truth.",
                lambda loc, st: f"Over-the-shoulder POV. We see what {prot} sees. {st[:80]} The frame is intimate, almost claustrophobic. Every detail sharpens.",
                lambda loc, st: f"Dynamic mid-action frame. Motion blur trails the movement. {st[:60]} The composition tilts — nothing is stable right now.",
                lambda loc, st: f"Stillness. A quiet beat. {st[:80]} The camera holds on the space between words. That's where the real story lives.",
                lambda loc, st: f"Low angle — the sky dominates. {st[:60]} Clouds drift like unspoken thoughts. The scale reminds us how small we are.",
                lambda loc, st: f"Detail insert. [ORIGINAL COMMENTARY PLACEHOLDER: unique close-up element specific to this chapter — an object, a symbol, a scar, a flower] {st[:40]}",
                lambda loc, st: f"Silhouette against a luminous backdrop. {st[:80]} The outline tells the story. Faces hidden. Emotions written in posture.",
                lambda loc, st: f"Wide shot. {loc} stretches before us. {st[:60]} [VISUAL OVERLAY: data-driven atmospheric effect — particle count, light intensity, color temperature shift]",
            ]

            visual_overlays = [
                None,
                None,
                None,
                None,
                "[ORIGINAL COMMENTARY PLACEHOLDER: character-driven narration layer — voiceover reflecting on the emotional weight of this specific moment]",
                None,
                "[VISUAL OVERLAY PLACEHOLDER: atmospheric particle effect — fireflies, falling leaves, drifting snow, embers rising]",
                None,
                None,
                "[ORIGINAL COMMENTARY PLACEHOLDER: unique data insight — panel count, scene duration, emotional arc measurement]",
            ]

            panels = []
            for pi in range(panel_count):
                st = scene_sentences[pi % max(len(scene_sentences), 1)]
                pt = panel_seq[pi % len(panel_seq)]

                comp = comp_generators[pi % len(comp_generators)](loc, st)

                if visual_overlays[pi % len(visual_overlays)]:
                    comp += f" {visual_overlays[pi % len(visual_overlays)]}"

                char_combo = mentioned[:min(pi + 1, len(mentioned))]
                if not char_combo:
                    char_combo = [prot]
                char_combo = list(set(c.capitalize() for c in char_combo))

                dia = None
                if pt in ("character_focus", "character_interaction", "action"):
                    if pi > 0 and pi < panel_count - 1:
                        words_list = st.split()
                        if len(words_list) > 6:
                            mid = max(3, len(words_list) // 2)
                            speaker = random.choice(char_combo)
                            dia_text = " ".join(words_list[:mid])
                            dia = {"speaker": speaker, "text": dia_text + "...", "dialogue_type": random.choice(["default", "whisper", "default", "default", "yell"])}

                th = scene_sentences[min(pi, len(scene_sentences) - 1)]
                if th and len(th) > 120:
                    th = th[:117] + "..."

                if pi == 0:
                    comp = f"Wide establishing shot of {loc}. {st[:80]} Light pours in like a promise. [VISUAL OVERLAY: scene-level color grade — warm amber / cool teal / golden hour spectrum]"
                    char_combo = []
                    th = None
                elif pi == 1:
                    comp = f"Medium shot — the space becomes inhabited. {st[:80]} Characters enter the frame. The story begins to breathe."
                elif pi == panel_count - 1:
                    close = scene_sentences[-1] if scene_sentences else st
                    comp = f"[CLOSING SHOT] {close[:120]} {loc} bathed in transitional light. The frame holds. A beat of silence before the page turns."

                panels.append({
                    "panel_num": pi + 1,
                    "type": pt,
                    "composition": comp,
                    "characters": char_combo,
                    "dialogue": dia,
                    "thought": th,
                })

            scene_configs.append({
                "id": f"{ch_num}.{sn}",
                "scene_num": sn,
                "location": loc,
                "mood": mood,
                "narration": narration,
                "panels": panels,
            })

        scenes = scene_configs

    return {
        "title": f"Chapter {ch_num}: {title}",
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
    parser.add_argument("--output", type=str, help="Output path for chapter script")
    args = parser.parse_args()

    if args.list:
        list_chapters()
    else:
        out = args.output or str(ROOT / "output" / "trial" / "chapter_script.json")
        script = generate_chapter(args.chapter, output_path=out)
        if script:
            print(json.dumps(script, indent=2, ensure_ascii=False)[:2000])
            print(f"\n... ({len(json.dumps(script))} total chars)")
