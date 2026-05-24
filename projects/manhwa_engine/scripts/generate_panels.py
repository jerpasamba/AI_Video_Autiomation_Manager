import os
import json
import logging
import time
import random
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent.parent

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
]

QUALITY_PREFIX = "masterpiece, best quality, highly detailed, sharp focus, award-winning illustration."

STYLE_TAG = (
    f"{QUALITY_PREFIX} "
    "Anime webtoon manhwa style, cel-shaded fantasy art, "
    "warm vibrant color palette, soft gradients, natural lighting, "
    "clean crisp lineart, smooth rendering, "
    "digital painting, high resolution illustration, "
    "vertical webtoon composition, "
    "PERFECT human anatomy: symmetrical eyes, natural 5-fingered hands with proper thumb opposition, "
    "correct shoulder-to-waist proportions, natural head size, "
    "no extra fingers, no missing fingers, no distorted limbs, no broken anatomy, "
    "not photorealistic, not 3D rendered, pure anime aesthetic"
)

NEGATIVE_STYLE = (
    "mutated hands, extra fingers, missing fingers, deformed hands, "
    "bad anatomy, wrong anatomy, extra limbs, missing limbs, "
    "distorted face, bad eyes, crossed eyes, asymmetrical eyes, "
    "malformed limbs, cloned face, disfigured, "
    "low quality, blurry, jpeg artifacts, watermark, signature, text"
)

CHARACTER_APPEARANCES = {
    "lian": "Lian: 5yo cute boy, messy silver-white hair, big bright blue eyes that sparkle with curiosity, rosy cheeks, small for his age but always smiling. Wears simple village clothes — a cream linen shirt, brown shorts, and a small blue cape his grandmother made him. Carries a small wooden staff decorated with shiny rocks.",
    "nora": "Nora: 7yo girl, messy ginger hair in two pigtails, face full of freckles, bright green eyes full of mischief, missing a front tooth, always has skinned knees. Wears a patched green dress and carries a tiny wooden shield. Energetic and loud.",
    "finn": "Finn: 14yo boy, tall and lanky, floppy brown hair that falls in his eyes, warm hazel eyes, calloused hands from blacksmith work, always has a smudge of soot on his nose. Wears a simple grey tunic and leather apron. Grumpy expression hiding a kind heart.",
    "may": "Elder May: 70yo woman, short with silver hair in an elegant bun, warm brown skin crinkled with smile lines, kind dark eyes, wears a handmade floral dress with a hand-knitted shawl. Walks with a sturdy cane that glows faintly. Grandmotherly and wise.",
    "brock": "Guild Master Brock: 45yo burly man, thick brown beard streaked with grey, one eye covered by a leather patch, muscular build gone slightly soft, warm brown visible eye, friendly scar across his nose. Wears a well-worn leather vest over a stained shirt.",
    "ember": "Ember the Fae Fox: magical fox creature the size of a small dog, sleek orange-red fur with a flame-patterned tail, golden eyes with slit pupils, pointed ears with tufts, leaves a trail of tiny floating light motes when moving, curious and playful expression",
}


def get_char_desc(char_name):
    nl = char_name.lower().strip()
    for key, desc in CHARACTER_APPEARANCES.items():
        if key in nl or nl in key:
            return desc
    return ""


def build_prompt(panel_info):
    ptype = panel_info.get("type", "default")
    composition = panel_info.get("composition", panel_info.get("description", ""))
    chars = panel_info.get("characters", [])
    comp_lower = composition.lower()

    has_characters = len(chars) > 0 and not all(
        c.lower() in ["", "none", "scene", "everyone"] for c in chars
    )

    # NEW SHOT TYPE DETECTION — expanded for 16 types
    is_abstract_est = ptype == "abstract_establishing" or any(w in comp_lower for w in ["abstract cosmic", "first rift", "energy visualization"])
    is_environment = any((
        ptype in ["environment", "establishing"],
        any(w in comp_lower for w in ["wide environmental", "landscape", "shot of city", "skyline", "location shot"]),
    ))
    is_detail_env = ptype == "detail_environment" or any(w in comp_lower for w in ["ground-level", "texture of", "close-up of environment", "environmental detail", "surface detail"])
    is_ui = any((
        ptype == "ui_focus",
        any(w in comp_lower for w in ["ui focus", "interface", "system panel", "system interface", "holographic", "float in darkness", "floating display", "notification"]),
    ))
    is_obj_detail = any((
        ptype == "object_detail",
        any(w in comp_lower for w in ["extreme close-up of", "macro shot", "close-up of", "object detail", "item focus", "phone screen", "pendant"]),
        ptype == "object_detail",
    ))
    is_hands = ptype == "hands_only" or any(w in comp_lower for w in ["hands-only", "hands only", "close-up of hands", "hands held"])
    is_char_focus = any((
        ptype == "character_focus",
        any(w in comp_lower for w in ["medium shot", "character in environment", "side-angle"]),
    ))
    is_reaction = any((
        ptype == "reaction",
        any(w in comp_lower for w in ["close-up face", "reaction shot", "emotion", "terrified", "shocked"]),
    ))
    is_silhouette = any((
        ptype == "silhouette",
        any(w in comp_lower for w in ["silhouette", "backlit", "outlined in", "dramatic silhouette"]),
    ))
    is_thought_focus = any((
        ptype == "thought_focus",
        any(w in comp_lower for w in ["thought", "contemplative", "from behind", "looking", "pensive", "introspective"]),
    ))
    is_action = any((
        ptype == "action",
        any(w in comp_lower for w in ["action", "dynamic", "running", "dodging", "sprinting", "lunging", "mid-action", "movement"]),
        not any(w in comp_lower for w in ["freeze", "impact", "pov"]),
    ))
    is_impact = any((
        ptype == "impact_freeze",
        any(w in comp_lower for w in ["freeze-frame", "frozen moment", "impact shot", "peak moment", "exact moment of impact", "frozen peak", "shockwave"]),
    ))
    is_pov = any((
        ptype == "pov_action",
        any(w in comp_lower for w in ["pov", "first-person", "through ren's eyes", "attacker's perspective", "perspective shot"]),
    ))
    is_lowangle = any((
        ptype == "low_angle_threat",
        any(w in comp_lower for w in ["low-angle", "low angle", "from ground level looking", "towering over"]),
    ))
    is_aftermath = any((
        ptype == "aftermath",
        any(w in comp_lower for w in ["aftermath", "atmospheric", "dissipating", "drifting", "settling", "empty", "dust settling"]),
    ))
    is_scaleshot = any((
        ptype == "scale_shot",
        any(w in comp_lower for w in ["extreme wide", "massive scale", "tiny figure", "barely visible", "far above", "dwarfed"]),
    ))

    shot_style = ""
    if is_abstract_est:
        shot_style = "Anime abstract cosmic visual composition, pure atmospheric energy and light, no defined geography, ethereal dimensional aesthetic, otherworldly. "
    elif is_environment:
        shot_style = "Anime wide atmospheric landscape shot, world-building focus, cinematic depth, environmental storytelling. "
    elif is_detail_env:
        shot_style = "Anime close-up environmental texture shot, sharp detail on surface/wall/ground, atmospheric mood through texture, shallow depth of field. "
    elif is_ui:
        shot_style = "Anime translucent holographic interface UI focus, floating dark-purple display panel with silver runic borders, text materializing letter by letter, ripple patterns. "
    elif is_obj_detail:
        shot_style = "Anime extreme close-up macro detail shot, sharp focus on single object, shallow depth of field, texture emphasis, dramatic lighting on subject. "
    elif is_hands:
        shot_style = "Anime close-up hands-only shot, expressive hand posture, no face visible, emotional weight through hands and fingers, detail of skin and texture. "
    elif is_char_focus:
        shot_style = "Anime medium shot of character in environment, character prominent but setting visible, natural pose, cinematic framing. "
    elif is_reaction:
        shot_style = "Anime tight close-up of face, extreme emotion visible, dramatic shadows across half the face, intense eye expression, shallow focus. "
    elif is_silhouette:
        shot_style = "Anime dramatic silhouette shot, dark figure against bright light source, strong light-dark contrast, minimal visible interior detail, backlit rim light. "
    elif is_thought_focus:
        shot_style = "Anime contemplative shot from behind or side angle, character facing away from viewer, quiet atmosphere, pensive mood, soft lighting. "
    elif is_action:
        shot_style = "Anime dynamic mid-action movement shot, motion blur, energetic angle, speed lines, kinetic composition, dramatic pose. "
    elif is_impact:
        shot_style = "Anime frozen peak-action freeze frame, mid-impact moment frozen in time, shockwave visible, debris suspended, cracks spreading, energy burst at contact point. "
    elif is_pov:
        shot_style = "Anime first-person POV perspective shot, immersive angle showing what character sees, cinematic view, foreground elements slightly blurred, hands/weapons at bottom edge. "
    elif is_lowangle:
        shot_style = "Anime dramatic low-angle shot looking upward, subject appears large and imposing, skewed perspective, sense of power imbalance or being overwhelmed. "
    elif is_aftermath:
        shot_style = "Anime atmospheric aftermath shot, quiet tension after action, settling particles or debris, empty space as character, stillness, moody lighting. "
    elif is_scaleshot:
        shot_style = "Anime extreme wide shot emphasizing massive scale, vast environment dominating frame, subject tiny or barely visible, sense of isolation and awe. "
    else:
        shot_style = "Anime wide establishing shot, atmospheric location focus, cinematic framing. "

    # Character appearance descriptions
    char_appearance_text = ""
    if has_characters:
        seen = set()
        parts = []
        for c in chars:
            nl = c.lower().strip()
            if nl not in seen and nl not in ["", "none", "everyone", "voidspawn"]:
                seen.add(nl)
                desc = get_char_desc(c)
                if desc:
                    parts.append(desc)
        if parts:
            char_appearance_text = "CHARACTER DESIGNS: " + "; ".join(parts) + ". "

    char_name_mentioned = any(c.lower().split()[0] in comp_lower for c in chars) if chars else False
    include_char_desc = has_characters and char_name_mentioned

    prompt = f"{shot_style}Anime scene: {composition}. "
    if include_char_desc and char_appearance_text:
        prompt += f"{char_appearance_text}"
    prompt += f"{STYLE_TAG}."
    return prompt


def generate_panel_via_pollinations(prompt, output_path, width=1920, height=1080, seed=None):
    base_url = "https://image.pollinations.ai/prompt"
    encoded = urllib.parse.quote(prompt)
    if seed is None:
        seed = random.randint(0, 99999)
    neg = urllib.parse.quote(NEGATIVE_STYLE)
    url = f"{base_url}/{encoded}?width={width}&height={height}&seed={seed}&negative={neg}&model=flux"

    for attempt in range(5):
        try:
            ua = random.choice(_USER_AGENTS)
            req = urllib.request.Request(url, headers={"User-Agent": ua})
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = resp.read()
            if len(data) < 2000:
                log.warning("Response too small (%d bytes), retrying...", len(data))
                time.sleep(3)
                continue
            with open(output_path, "wb") as f:
                f.write(data)
            log.info("Saved: %s (%d bytes)", os.path.basename(output_path), len(data))
            return True
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 15 * (attempt + 1)
                log.warning("Rate limited 429, waiting %ds...", wait)
                time.sleep(wait)
                continue
            log.warning("HTTP %d: %s", e.code, str(e)[:80])
            time.sleep(5)
            continue
        except Exception as e:
            log.warning("Error: %s", str(e)[:80])
            time.sleep(5)
            continue
    return False


def generate_all_panels(script, output_dir=None, panel_width=1920, panel_height=1080):
    if output_dir is None:
        output_dir = ROOT / "output" / "Final" / "ch01" / "panels"
    else:
        output_dir = Path(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    panel_map = {}
    scenes = script.get("scenes", [])

    for scene in scenes:
        snum = scene.get("scene_num", 1)
        scene_seed = snum * 12345

        for panel in scene.get("panels", []):
            pnum = panel.get("panel_num", 1)
            fname = f"s{snum:02d}_p{pnum:02d}.png"
            fpath = output_dir / fname

            if fpath.exists():
                log.info("Panel %s already exists, skipping", fname)
                panel_map[f"{snum}_{pnum}"] = str(fpath)
                continue

            prompt = build_prompt(panel)
            panel_seed = scene_seed + pnum
            log.info("Gen s%02d_p%02d (seed=%d type=%s)", snum, pnum, panel_seed, panel.get("type", ""))

            success = generate_panel_via_pollinations(prompt, str(fpath), panel_width, panel_height, seed=panel_seed)
            if success:
                panel_map[f"{snum}_{pnum}"] = str(fpath)
            else:
                log.warning("Panel s%02d_p%02d failed, placeholder", snum, pnum)
                _create_placeholder(str(fpath), panel_width, panel_height, panel.get("type", ""))
                panel_map[f"{snum}_{pnum}"] = str(fpath)

            delay = 6
            time.sleep(delay)

    return panel_map


def _create_placeholder(output_path, w=1920, h=1080, ptype=""):
    try:
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGB", (w, h), (240, 240, 235))
        draw = ImageDraw.Draw(img)
        draw.rectangle([10, 10, w - 10, h - 10], outline=(200, 200, 195), width=2)
        font = ImageFont.truetype("arial.ttf", 28)
        label = ptype.replace("_", " ").title() if ptype else "Panel"
        bb = draw.textbbox((0, 0), label, font=font)
        draw.text(((w - (bb[2] - bb[0])) // 2, (h - (bb[3] - bb[1])) // 2 - 30), label, fill=(180, 180, 175), font=font)
        sub = "[placeholder]"
        bb2 = draw.textbbox((0, 0), sub, font=font)
        draw.text(((w - (bb2[2] - bb2[0])) // 2, (h - (bb2[3] - bb2[1])) // 2 + 20), sub, fill=(200, 200, 195), font=font)
        img.save(output_path)
    except Exception as e:
        log.error("Placeholder failed: %s", e)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    script_path = ROOT / "output" / "trial" / "chapters" / "chapter_01.json"
    if script_path.exists():
        with open(script_path) as f:
            script = json.load(f)
        pm = generate_all_panels(script, panel_width=1080, panel_height=800)
        print(f"Generated {len(pm)} panels")
