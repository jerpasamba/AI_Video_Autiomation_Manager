import os
import json
import math
import random
import logging
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent.parent

_FONT_CACHE = {}

def _get_font(size=24, bold=False):
    key = (size, bold)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    candidates = [
        "C:/Windows/Fonts/impact.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                f = ImageFont.truetype(path, size)
                _FONT_CACHE[key] = f
                return f
            except Exception:
                continue
    f = ImageFont.load_default()
    _FONT_CACHE[key] = f
    return f


def _find_magic_panel(script, panels_dir):
    scenes = script.get("scenes", [])

    def has_active_magic(comp):
        c = comp.lower()
        magic_phrases = [
            "cast", "glow", "starlight", "mana sight", "light magic",
            "golden thread", "silver glow", "spell", "energy",
            "channeling", "magic extending",
        ]
        return any(p in c for p in magic_phrases)

    for scene in reversed(scenes):
        snum = scene.get("scene_num", 1)
        for panel in scene.get("panels", []):
            pnum = panel.get("panel_num", 1)
            ptype = panel.get("type", "")
            comp = panel.get("composition", "")
            chars = panel.get("characters", [])
            has_lian = any("lian" in c.lower() for c in chars)
            if not has_lian:
                continue
            if ptype == "action" and has_active_magic(comp):
                fname = f"s{snum:02d}_p{pnum:02d}.png"
                fpath = Path(panels_dir) / fname
                if fpath.exists():
                    return fpath

    for scene in reversed(scenes):
        snum = scene.get("scene_num", 1)
        for panel in scene.get("panels", []):
            pnum = panel.get("panel_num", 1)
            ptype = panel.get("type", "")
            comp = panel.get("composition", "")
            chars = panel.get("characters", [])
            has_lian = any("lian" in c.lower() for c in chars)
            if not has_lian:
                continue
            if ptype in ("character_focus", "reaction") and has_active_magic(comp):
                fname = f"s{snum:02d}_p{pnum:02d}.png"
                fpath = Path(panels_dir) / fname
                if fpath.exists():
                    return fpath

    for scene in reversed(scenes):
        snum = scene.get("scene_num", 1)
        for panel in scene.get("panels", []):
            pnum = panel.get("panel_num", 1)
            ptype = panel.get("type", "")
            chars = panel.get("characters", [])
            has_lian = any("lian" in c.lower() for c in chars)
            if not has_lian:
                continue
            if ptype in ("reaction", "character_focus", "action"):
                fname = f"s{snum:02d}_p{pnum:02d}.png"
                fpath = Path(panels_dir) / fname
                if fpath.exists():
                    return fpath

    for scene in reversed(scenes):
        snum = scene.get("scene_num", 1)
        for panel in scene.get("panels", []):
            pnum = panel.get("panel_num", 1)
            fname = f"s{snum:02d}_p{pnum:02d}.png"
            fpath = Path(panels_dir) / fname
            if fpath.exists():
                return fpath
    return None


def _radial_glow(size, center, radius, color, max_alpha=80):
    """Return an RGBA overlay with a radial glow centered at (cx, cy)."""
    w, h = size
    cx, cy = center
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(glow)
    for r in range(radius, 0, -4):
        a = int(max_alpha * (1 - r / radius))
        if a > 0:
            draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                         fill=(*color, a))
    return glow


def _sparkles(size, count=40):
    """Return an RGBA overlay with random sparkle dots."""
    w, h = size
    sp = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(sp)
    rng = random.Random(42)
    for _ in range(count):
        x = rng.randint(0, w - 1)
        y = rng.randint(0, h - 1)
        rad = rng.randint(2, 6)
        alpha = rng.randint(60, 200)
        sat = rng.randint(200, 255)
        color = (sat, rng.randint(180, sat), rng.randint(40, 120), alpha)
        draw.ellipse([x - rad, y - rad, x + rad, y + rad], fill=color)
    return sp


def _energy_lines(draw, cx, cy, color, count=12, length=100):
    """Draw energy/light beams radiating from a point."""
    for i in range(count):
        angle = 2 * math.pi * i / count + random.uniform(-0.1, 0.1)
        l = length + random.randint(-20, 20)
        ex = cx + math.cos(angle) * l
        ey = cy + math.sin(angle) * l
        for t in range(0, l, 4):
            px = int(cx + math.cos(angle) * t)
            py = int(cy + math.sin(angle) * t)
            a = int(180 * (1 - t / l))
            draw.point((px, py), fill=(*color, a))


OP_TEXTS = {
    1: [["STAR", "CHILD"], ["FALLEN", "STAR"], ["NOT", "ORDINARY"]],
    2: [["STARLIGHT", "WEAVE"], ["MANA", "SIGHT"], ["NEW", "SPELL"]],
    3: [["RANK S", "MAGIC"], ["FORGOTTEN", "ABILITY"], ["TOO", "STRONG"]],
    4: [["GOD", "TIER"], ["SECRET", "POWER"], ["AWAKENED"]],
    5: [["LEGENDARY", "MAGIC"], ["UNSTOPPABLE"], ["OVER", "POWERED"]],
}


def generate_thumbnail(chapter_num, chapter_title, script, output_dir, panels_dir):
    output_path = Path(output_dir) / "thumbnail.jpg"
    thumb_w, thumb_h = 1280, 720

    bg_path = _find_magic_panel(script, panels_dir)
    if bg_path and bg_path.exists():
        bg_raw = Image.open(bg_path).convert("RGB")
        log.info("Thumbnail bg: %s", bg_path.name)
    else:
        bg_raw = Image.new("RGB", (thumb_w, thumb_h), (5, 2, 15))

    bg_raw = bg_raw.resize((thumb_w, thumb_h), Image.LANCZOS)

    bg_raw = bg_raw.filter(ImageFilter.GaussianBlur(radius=1))
    bg_raw = ImageOps.autocontrast(bg_raw, cutoff=2)

    # --- energy glow overlay ---
    cx, cy = thumb_w // 2, thumb_h // 2 - 40
    glow = _radial_glow((thumb_w, thumb_h), (cx, cy), 350, (255, 200, 100), max_alpha=50)
    bg = Image.alpha_composite(bg_raw.convert("RGBA"), glow)

    # --- vignette overlay ---
    vignette = Image.new("RGBA", (thumb_w, thumb_h), (0, 0, 0, 0))
    vdraw = ImageDraw.Draw(vignette)
    for y in range(thumb_h):
        t = y / thumb_h
        a = int(100 * t * t * t)
        if a > 0:
            vdraw.line([(0, y), (thumb_w, y)], fill=(0, 0, 0, a))
    for x in range(thumb_w):
        t = min(x, thumb_w - x) / (thumb_w // 2)
        a = int(50 * (1 - t) * (1 - t))
        if a > 2 and a > 0:
            vdraw.line([(x, 0), (x, thumb_h)], fill=(0, 0, 0, a))

    # --- energy beams from center ---
    random.seed(42)
    _energy_lines(vdraw, cx, cy, (255, 180, 50), count=14, length=160)

    bg = Image.alpha_composite(bg, vignette)

    # --- sparkles ---
    sparkles = _sparkles((thumb_w, thumb_h), count=50)
    bg = Image.alpha_composite(bg, sparkles)

    draw = ImageDraw.Draw(bg)

    # --- series tag top-left ---
    tag_font = _get_font(18, bold=True)
    draw.text((15, 15), "The Star-Touched Boy", fill=(255, 255, 255, 200), font=tag_font)

    # --- chapter badge ---
    ch_font = _get_font(22, bold=True)
    ch_txt = f"Ch.{chapter_num}"
    bb = draw.textbbox((0, 0), ch_txt, font=ch_font)
    bw, bh = bb[2] - bb[0], bb[3] - bb[1]
    pad = 6
    draw.rectangle([15, 40, 15 + bw + pad * 2, 40 + bh + pad * 2], fill=(200, 30, 30, 220))
    draw.text((15 + pad, 40 + pad), ch_txt, fill=(255, 255, 255), font=ch_font)

    # --- ability name in giant glowing text ---
    lines = OP_TEXTS.get(chapter_num, [["NEW", "MAGIC"]])[0]
    op_font = _get_font(90, bold=True)
    sub_font = _get_font(32, bold=False)

    total_h = 0
    line_boxes = []
    for line in lines:
        bb = draw.textbbox((0, 0), line, font=op_font)
        lw, lh = bb[2] - bb[0], bb[3] - bb[1]
        line_boxes.append((line, lw, lh))
        total_h += lh + 6

    text_cx = thumb_w // 2
    text_start_y = thumb_h - 110 - total_h

    for li, (line, lw, lh) in enumerate(line_boxes):
        lx = text_cx - lw // 2
        ly = text_start_y + li * (lh + 6)

        for dx in range(-5, 6):
            for dy in range(-5, 6):
                if dx * dx + dy * dy <= 20:
                    draw.text((lx + dx, ly + dy), line, fill=(0, 0, 0, 200), font=op_font)

        draw.text((lx - 2, ly - 2), line, fill=(255, 120, 40), font=op_font)
        draw.text((lx, ly), line, fill=(255, 255, 100), font=op_font)

    # --- accent line ---
    line_y = text_start_y - 18
    mid = thumb_w // 2
    for dx in range(-250, 251):
        intensity = int(200 + 55 * math.sin(dx / 50))
        draw.point((mid + dx, line_y), fill=(intensity, intensity // 2, 0, 220))

    # --- CTA text below ---
    cta_text = "NEW POWER UNLOCKED"
    cta_font = _get_font(38, bold=True)
    cbb = draw.textbbox((0, 0), cta_text, font=cta_font)
    cw = cbb[2] - cbb[0]
    cta_x = (thumb_w - cw) // 2
    cta_y = thumb_h - 40
    for dx in range(-3, 4):
        for dy in range(-3, 4):
            draw.text((cta_x + dx, cta_y + dy), cta_text, fill=(0, 0, 0, 200), font=cta_font)
    draw.text((cta_x, cta_y), cta_text, fill=(255, 200, 50), font=cta_font)

    bg.convert("RGB").save(output_path, "JPEG", quality=92)
    log.info("Thumbnail saved: %s", output_path)
    return str(output_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    import sys
    ch = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    out_dir = ROOT / "output" / "Final" / f"ch{ch:02d}"
    script_path = out_dir / "script.json"
    if script_path.exists():
        with open(script_path, encoding="utf-8") as f:
            script = json.load(f)
        title = script.get("title", f"Chapter {ch}")
        ch_title = title.replace(f"Chapter {ch}: ", "").replace(f"Chapter {ch}", "").strip()
        generate_thumbnail(ch, ch_title, script, out_dir, out_dir / "panels")
    else:
        log.error("Script not found: %s", script_path)
