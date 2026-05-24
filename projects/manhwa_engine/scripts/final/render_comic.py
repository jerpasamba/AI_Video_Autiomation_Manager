import os, json, logging, subprocess, math, tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import cv2

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent.parent.parent

from app.subprocess_utils import no_console_kwargs

_FONT_CACHE = {}

def get_font(size=24, bold=False):
    key = (size, bold)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    candidates = [
        "C:/Windows/Fonts/malgun.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
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

def get_ffmpeg_path():
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        return get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"

def _draw_glow_text(draw, text, font, x, y, text_color, glow_color, glow_radius=3):
    for dx in range(-glow_radius, glow_radius + 1):
        for dy in range(-glow_radius, glow_radius + 1):
            if dx * dx + dy * dy <= glow_radius * glow_radius:
                draw.text((x + dx, y + dy), text, fill=glow_color, font=font)
    draw.text((x, y), text, fill=text_color, font=font)

def generate_title_card(chapter_num, chapter_title, output_path, viewport_w=1920, viewport_h=1080):
    img = Image.new("RGB", (viewport_w, viewport_h), (5, 2, 15))
    draw = ImageDraw.Draw(img)

    for y in range(viewport_h):
        t = y / viewport_h
        v = int(8 + 12 * math.sin(t * math.pi))
        draw.line([(0, y), (viewport_w, y)], fill=(v, v // 3, v + 8))

    for x in range(0, viewport_w, 60):
        a = int(6 + 4 * math.sin(x / 300))
        draw.line([(x, 0), (x, viewport_h)], fill=(a, a // 2, a + 4), width=1)

    cx, cy = viewport_w // 2, viewport_h // 2

    corner_off = 80
    ccol = (80, 40, 160)
    for sign in [-1, 1]:
        draw.line([(cx + sign * 400, cy + sign * 250), (cx + sign * 400, cy + sign * 300)], fill=ccol, width=3)
        draw.line([(cx + sign * 400, cy + sign * 250), (cx + sign * 350, cy + sign * 250)], fill=ccol, width=3)
        draw.line([(cx + sign * 400, cy + sign * 250), (cx + sign * 400, cy + sign * 200)], fill=ccol, width=3)

    lbl_font = get_font(28)
    lbl = f"— CHAPTER {chapter_num} —"
    bb = draw.textbbox((0, 0), lbl, font=lbl_font)
    _draw_glow_text(draw, lbl, lbl_font,
                    cx - (bb[2] - bb[0]) // 2, cy - 110,
                    (200, 170, 255), (60, 30, 120), 2)

    import re as _re
    clean = _re.sub(r'^Chapter\s+\d+[\s:–\-]+', '', chapter_title, flags=_re.IGNORECASE)
    title_font = get_font(52)
    words = clean.split()
    lines = []
    cur = []
    for w in words:
        cur.append(w)
        line = " ".join(cur)
        tw = draw.textbbox((0, 0), line, font=title_font)[2]
        if tw > 800 and len(cur) > 1:
            lines.append(" ".join(cur[:-1]))
            cur = [w]
    if cur:
        lines.append(" ".join(cur))
    lines = lines[:3]

    ty = cy - 60
    for li, line in enumerate(lines):
        bb = draw.textbbox((0, 0), line, font=title_font)
        lx = cx - (bb[2] - bb[0]) // 2
        _draw_glow_text(draw, line, title_font, lx, ty + li * 60,
                        (240, 230, 255), (0, 0, 0), 4)
        bb = draw.textbbox((0, 0), line, font=title_font)
        draw.text((lx + 2, ty + li * 60 + 2), line, fill=(120, 80, 200), font=title_font)
        draw.text((lx, ty + li * 60), line, fill=(245, 240, 255), font=title_font)

    draw.line([(cx - 200, cy + 100), (cx + 200, cy + 100)], fill=(100, 60, 180), width=1)

    sub_font = get_font(26)
    sub = "The Star-Touched Boy"
    bb = draw.textbbox((0, 0), sub, font=sub_font)
    _draw_glow_text(draw, sub, sub_font,
                    cx - (bb[2] - bb[0]) // 2, cy + 115,
                    (180, 160, 220), (40, 20, 80), 2)

    img.save(output_path)
    log.info("Title card saved: %s", output_path)
    return str(output_path)

def _split_for_subs(text, max_chars=80):
    flat = text.replace("\n", " ").replace("\r", "")
    words = flat.split()
    chunks = []
    cur = ""
    for w in words:
        if len(cur) + len(w) + 1 > max_chars and cur:
            chunks.append(cur.strip())
            cur = w
        else:
            cur = cur + " " + w if cur else w
    if cur:
        chunks.append(cur.strip())
    return chunks if chunks else [flat]

def generate_script_subtitles(script, audio_duration, output_path, title_duration=5.0):
    scenes = script.get("scenes", [])
    num_scenes = len(scenes)
    scene_avail = max(audio_duration - title_duration, 1.0)
    scene_len = scene_avail / max(num_scenes, 1)
    all_chunks = []
    for si, scene in enumerate(scenes):
        for n in scene.get("narration", []):
            for chunk in _split_for_subs(n):
                all_chunks.append((chunk, si))
        for panel in scene.get("panels", []):
            d = panel.get("dialogue")
            if d and d.get("text"):
                for chunk in _split_for_subs(d["text"]):
                    all_chunks.append((chunk, si))
            thought = panel.get("thought")
            if thought:
                for chunk in _split_for_subs(thought):
                    all_chunks.append((chunk, si))
    if not all_chunks:
        return str(output_path)
    from collections import defaultdict
    scene_chunks = defaultdict(list)
    for text, si in all_chunks:
        scene_chunks[si].append(text)
    with open(output_path, "w", encoding="utf-8") as f:
        idx = 1
        for si in range(num_scenes):
            entries = scene_chunks.get(si, [])
            if not entries:
                continue
            scene_start = title_duration + si * scene_len
            scene_end = title_duration + (si + 1) * scene_len
            per_entry = scene_len / max(len(entries), 1)
            for li, text in enumerate(entries):
                start = scene_start + li * per_entry
                end = min(start + per_entry, scene_end)
                h, m, s = int(start // 3600), int((start % 3600) // 60), int(start % 60)
                ms = int((start - int(start)) * 1000)
                start_str = f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
                h, m, s = int(end // 3600), int((end % 3600) // 60), int(end % 60)
                ms = int((end - int(end)) * 1000)
                end_str = f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
                f.write(f"{idx}\n{start_str} --> {end_str}\n{text}\n\n")
                idx += 1
    count = idx - 1
    log.info("Generated %d subtitle entries", count)
    return str(output_path)

def _shift_srt(src, dst, offset_sec):
    with open(src, encoding="utf-8") as f:
        content = f.read()
    def _shift_time(m):
        h, m_s, s_ms = m.group(0).split(":")
        s, ms = s_ms.split(",")
        total = int(h)*3600 + int(m_s)*60 + int(s) + int(ms)/1000 + offset_sec
        nh = int(total // 3600)
        nm = int((total % 3600) // 60)
        ns = int(total % 60)
        nms = int((total - int(total)) * 1000)
        return f"{nh:02d}:{nm:02d}:{ns:02d},{nms:03d}"
    import re
    shifted = re.sub(r"\d{2}:\d{2}:\d{2},\d{3}", _shift_time, content)
    with open(dst, "w", encoding="utf-8") as f:
        f.write(shifted)
    log.info("Shifted subtitles by %.1fs -> %s", offset_sec, dst)

def render_comic(panel_video_path, audio_path, output_path=None, bgm_path=None):
    if output_path is None:
        output_path = ROOT / "output" / "Final" / "ch01" / "chapter_01_video.mp4"
    else:
        output_path = Path(output_path)
    os.makedirs(output_path.parent, exist_ok=True)

    out_dir = output_path.parent
    script_path = out_dir / "script.json"
    chapter_title = "Chapter 1"
    ch_num = 1
    if script_path.exists():
        with open(script_path, encoding="utf-8") as f:
            sc = json.load(f)
        chapter_title = sc.get("title", chapter_title)
        import re as _re
        m = _re.search(r'Chapter\s+(\d+)', chapter_title)
        if m:
            ch_num = int(m.group(1))

    title_path = out_dir / "title_card.png"
    generate_title_card(ch_num, chapter_title, str(title_path))
    title_scene_path = out_dir / "title_card_video.mp4"
    title_duration = 5.0

    _create_title_video(str(title_path), str(title_scene_path), title_duration)

    audio_duration = 30.0
    try:
        from moviepy import AudioFileClip
        audio = AudioFileClip(str(audio_path))
        audio_duration = audio.duration
        audio.close()
    except Exception:
        pass

    word_timed_subs = out_dir / "subtitles.srt"
    subs_path = out_dir / "subtitles_script.srt"
    if word_timed_subs.exists():
        # Shift word-timed subtitles by title_duration to account for title card
        _shift_srt(str(word_timed_subs), str(subs_path), title_duration)
    elif script_path.exists():
        with open(script_path, encoding="utf-8") as f:
            script_data = json.load(f)
        generate_script_subtitles(script_data, audio_duration, str(subs_path), title_duration=title_duration)

    log.info("Rendering final video...")
    result = _render_final(str(title_scene_path), str(panel_video_path), str(audio_path), str(subs_path), str(output_path), bgm_path, audio_delay=int(title_duration * 1000))
    return result

def _render_final(title_scene_path, panel_video_path, audio_path, subs_path, output_path, bgm_path=None, audio_delay=5000):
    ffmpeg = get_ffmpeg_path()

    has_subs = os.path.exists(subs_path)
    has_audio = audio_path and os.path.exists(audio_path)
    has_bgm = bgm_path and os.path.exists(bgm_path)

    inputs = ["-i", title_scene_path, "-i", panel_video_path]
    if has_audio:
        inputs += ["-i", audio_path]
    if has_bgm:
        inputs += ["-stream_loop", "-1", "-i", bgm_path]

    filter_parts = []
    amap = []

    vid_out = "vid"
    if has_subs:
        sf = subs_path.replace("\\", "/").replace(":", "\\\\:")
        vid_out = "vsub"
        filter_parts.append(f"[0:v][1:v]concat=n=2:v=1:a=0[vid]")
        filter_parts.append(f"[vid]subtitles={sf}:force_style='FontName=Arial\\:FontSize=20\\:PrimaryColour=&H00FFFFFF\\:OutlineColour=&H00000000\\:BorderStyle=1\\:Outline=2\\:Shadow=1\\:Alignment=2\\:MarginV=80'[{vid_out}]")
    else:
        filter_parts.append(f"[0:v][1:v]concat=n=2:v=1:a=0[{vid_out}]")

    audio_map = "[2:a]" if has_audio else ""
    if has_audio:
        filter_parts.append(f"{audio_map}adelay={audio_delay}|{audio_delay}[adel]")
        if has_bgm:
            bgm_idx = 3 if has_audio else 2
            filter_parts.append(f"[{bgm_idx}:a]volume=0.15[bgm]")
            filter_parts.append("[adel][bgm]amix=inputs=2:duration=first[aout]")
            amap = ["[aout]"]
        else:
            amap = ["[adel]"]

    cmd = [ffmpeg, "-y"] + inputs
    full_filter = ";".join(filter_parts)
    cmd += ["-filter_complex", full_filter]
    cmd += ["-map", f"[{vid_out}]"]
    if amap:
        cmd += ["-map", amap[0]]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
             "-c:a", "aac", "-b:a", "128k", "-shortest", output_path]

    log.info("Final encode with audio + subs...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600, **no_console_kwargs())
    if result.returncode != 0:
        log.error("FFmpeg error: %s", result.stderr[-1000:])
        return None

    if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
        log.info("Final video: %s (%.1f MB)", output_path, os.path.getsize(output_path) / (1024 * 1024))
        return output_path
    return None

def _create_title_video(title_card_path, output_path, duration=5.0, fps=20, viewport_w=1920, viewport_h=1080):
    ffmpeg = get_ffmpeg_path()
    tmpdir = tempfile.mkdtemp(prefix="title_")
    try:
        img = cv2.imread(title_card_path)
        if img is None:
            return False
        img = cv2.resize(img, (viewport_w, viewport_h), interpolation=cv2.INTER_LANCZOS4)
        for n in range(int(duration * fps)):
            frame = img.copy()
            frame = _blur_overlay(frame, viewport_w, viewport_h)
            frame = _vignette(frame, 0.15)
            cv2.imwrite(os.path.join(tmpdir, f"f{n:06d}.png"), frame)
        subprocess.run([ffmpeg, "-y", "-framerate", str(fps),
                         "-i", os.path.join(tmpdir, "f%06d.png"),
                         "-c:v", "libx264", "-preset", "superfast", "-crf", "23", "-pix_fmt", "yuv420p",
                         "-an", str(output_path)], capture_output=True, text=True, timeout=120, **no_console_kwargs())
    finally:
        for f in os.listdir(tmpdir):
            os.remove(os.path.join(tmpdir, f))
        os.rmdir(tmpdir)
    return os.path.getsize(output_path) > 1000

def _blur_overlay(frame, w, h, bw_r=0.10, br=35):
    bw = int(w * bw_r)
    for side in ["left", "right"]:
        r = frame[:, :bw] if side == "left" else frame[:, w - bw:]
        b = cv2.GaussianBlur(r, (br * 2 + 1, br * 2 + 1), 0)
        for x in range(bw):
            a = (float(bw - x) / bw if side == "left" else float(x + 1) / bw) * 0.7
            bl = (b[:, x] * a + r[:, x] * (1 - a)).astype(np.uint8)
            if side == "left":
                frame[:, x] = bl
            else:
                frame[:, w - bw + x] = bl
    return frame

def _vignette(frame, s=0.2):
    h, w = frame.shape[:2]
    kx = cv2.getGaussianKernel(w, w // 3)
    ky = cv2.getGaussianKernel(h, h // 3)
    m = 1 - ky * kx.T * s
    m = np.clip(m, 0, 1)
    for c in range(3):
        frame[:, :, c] = (frame[:, :, c] * m).astype(np.uint8)
    return frame
