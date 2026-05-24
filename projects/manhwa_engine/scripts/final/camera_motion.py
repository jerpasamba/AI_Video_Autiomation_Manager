import os, json, logging, subprocess, tempfile, math
from pathlib import Path
import numpy as np
import cv2

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent.parent.parent

from app.subprocess_utils import no_console_kwargs

def get_ffmpeg_path():
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        return get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"

def add_blur_overlay(frame, viewport_w, viewport_h, blur_width_ratio=0.03, blur_radius=3):
    h, w = frame.shape[:2]
    blur_w = int(w * blur_width_ratio)
    if blur_w < 2:
        return frame
    for side in ["left", "right"]:
        if side == "left":
            region = frame[:, :blur_w].copy()
            alphas = np.linspace(0.4, 0.0, blur_w, dtype=np.float32)
        else:
            region = frame[:, w - blur_w:].copy()
            alphas = np.linspace(0.0, 0.4, blur_w, dtype=np.float32)
        blurred = cv2.GaussianBlur(region, (blur_radius * 2 + 1, blur_radius * 2 + 1), 0).astype(np.float32)
        alphas = alphas.reshape(1, blur_w, 1)
        blend = (blurred * alphas + region.astype(np.float32) * (1 - alphas)).astype(np.uint8)
        if side == "left":
            frame[:, :blur_w] = blend
        else:
            frame[:, w - blur_w:] = blend
    return frame

def add_vignette(frame, strength=0.2):
    h, w = frame.shape[:2]
    kernel_x = cv2.getGaussianKernel(w, w // 3)
    kernel_y = cv2.getGaussianKernel(h, h // 3)
    mask = (1 - (kernel_y * kernel_x.T) * strength).astype(np.float32)
    mask = np.clip(mask, 0, 1)[:, :, np.newaxis]
    frame[:] = (frame.astype(np.float32) * mask).astype(np.uint8)
    return frame

def apply_color_boost(frame, sat=1.03, cont=1.02):
    try:
        f = frame.astype(np.float32)
        mean = cv2.mean(frame)[:3]
        f = (f - mean) * cont + mean
        f = np.clip(f, 0, 255).astype(np.uint8)
        hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] * sat, 0, 255)
        frame = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
    except Exception:
        pass
    return frame

def _fit_to_viewport(img, viewport_w, viewport_h):
    h, w = img.shape[:2]
    scale = max(viewport_w / w, viewport_h / h)
    new_w = int(w * scale)
    new_h = int(h * scale)
    if new_w % 2 != 0: new_w += 1
    if new_h % 2 != 0: new_h += 1
    new_w = min(new_w, 1920); new_h = min(new_h, 1920)
    scaled = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
    canvas = np.zeros((viewport_h, viewport_w, 3), dtype=np.uint8)
    x_off = max(0, (viewport_w - new_w) // 2)
    y_off = max(0, (viewport_h - new_h) // 2)
    actual_h = min(new_h, viewport_h - y_off)
    actual_w = min(new_w, viewport_w - x_off)
    canvas[y_off:y_off + actual_h, x_off:x_off + actual_w] = scaled[:actual_h, :actual_w]
    return canvas

def _ease_in_out(t):
    return t * t * (3 - 2 * t)

def _group_by_scene(panel_paths, panel_infos):
    groups = []
    cur_scene = None
    for path, info in zip(panel_paths, panel_infos):
        snum = info.get("scene_num", 1)
        if snum != cur_scene:
            groups.append([])
            cur_scene = snum
        groups[-1].append((path, info))
    return groups

def create_panel_video(all_panel_paths, all_panel_infos, output_path, audio_duration,
                        fps=5, viewport_w=1920, viewport_h=1080,
                        title_duration=5.0):
    if not all_panel_paths:
        log.error("No panels to render")
        return False

    MAX_VIDEO_SEC = 1800
    audio_duration = min(audio_duration, MAX_VIDEO_SEC)
    video_duration = max(audio_duration, 1.0)
    total_frames = int(video_duration * fps)
    trans_frames = max(1, int(0.3 * fps))

    scenes = _group_by_scene(all_panel_paths, all_panel_infos)
    num_scenes = len(scenes)

    total_trans = sum(max(len(s) - 1, 0) for s in scenes) * trans_frames
    usable_frames = max(total_frames - total_trans, total_frames // 2)
    scene_video_frames = usable_frames // max(num_scenes, 1)

    ffmpeg = get_ffmpeg_path()
    proc = subprocess.Popen(
         [ffmpeg, "-y", "-f", "rawvideo", "-vcodec", "rawvideo",
          "-s", f"{viewport_w}x{viewport_h}", "-pix_fmt", "bgr24",
          "-r", str(fps), "-i", "pipe:0",
          "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20",
          "-pix_fmt", "yuv420p", "-an", str(output_path)],
         stdin=subprocess.PIPE, stderr=subprocess.DEVNULL, **no_console_kwargs())
    try:
        frame_idx = 0
        panel_cache = {}
        for si, scene in enumerate(scenes):
            scene_panels = len(scene)
            if scene_panels == 0:
                continue
            if si == num_scenes - 1:
                hold_frames_per_panel = max(1, (usable_frames - frame_idx) // scene_panels)
            else:
                hold_frames_per_panel = max(1, scene_video_frames // scene_panels)
            for pi, (panel_path, pinfo) in enumerate(scene):
                log.info("Processing panel s%dp%d: %s", pinfo.get("scene_num", 0), pinfo.get("panel_num", 0), os.path.basename(panel_path))
                if not os.path.exists(panel_path):
                    blank = np.zeros((viewport_h, viewport_w, 3), dtype=np.uint8)
                    blank[:] = (35, 35, 35)
                    for _ in range(hold_frames_per_panel):
                        proc.stdin.write(blank.astype(np.uint8).tobytes())
                        frame_idx += 1
                    continue
                if panel_path in panel_cache:
                    base_frame = panel_cache[panel_path]
                else:
                    img = cv2.imread(panel_path)
                    if img is None:
                        log.warning("Could not read %s", panel_path)
                        continue
                    img = apply_color_boost(img)
                    base_frame = _fit_to_viewport(img, viewport_w, viewport_h)
                    panel_cache[panel_path] = base_frame

                ptype = pinfo.get("type", "")
                zoom_target = 1.0
                shake = 0
                if ptype in ["impact_freeze", "action"]:
                    shake = 6

                for fi in range(hold_frames_per_panel):
                    prog = fi / max(hold_frames_per_panel - 1, 1)
                    zoom = 1.0 + (zoom_target - 1.0) * prog
                    frame = _apply_zoom(base_frame, zoom, viewport_w, viewport_h)
                    if shake > 0:
                        sx = np.random.randint(-shake, shake + 1)
                        sy = np.random.randint(-shake, shake + 1)
                        M = np.float32([[1, 0, sx], [0, 1, sy]])
                        frame = cv2.warpAffine(frame, M, (viewport_w, viewport_h))
                    frame = add_blur_overlay(frame, viewport_w, viewport_h)
                    frame = add_vignette(frame, strength=0.05)
                    proc.stdin.write(frame.tobytes())
                    frame_idx += 1

                if pi < len(scene) - 1:
                    next_path = scene[pi + 1][0]
                    if os.path.exists(next_path):
                        next_img = cv2.imread(next_path)
                        if next_img is not None:
                            next_img = apply_color_boost(next_img)
                            next_frame = _fit_to_viewport(next_img, viewport_w, viewport_h)
                            fade_base = frame.copy()
                            for ti in range(trans_frames):
                                t = ti / max(trans_frames - 1, 1)
                                eased = _ease_in_out(t)
                                blend = cv2.addWeighted(fade_base, 1 - eased, next_frame, eased, 0)
                                blend = add_blur_overlay(blend, viewport_w, viewport_h)
                                blend = add_vignette(blend, strength=0.05)
                                proc.stdin.write(blend.tobytes())
                                frame_idx += 1

        if frame_idx < total_frames:
            pad = np.zeros((viewport_h, viewport_w, 3), dtype=np.uint8)
            pad[:] = (10, 5, 25)
            for _ in range(total_frames - frame_idx):
                proc.stdin.write(pad.tobytes())
                frame_idx += 1
    finally:
        proc.stdin.close()
        proc.wait()

    size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
    if size > 1000:
        log.info("Panel video OK: %s (%d KB)", os.path.basename(output_path), size // 1024)
        return True
    return False

def _apply_zoom(frame, zoom_factor, viewport_w, viewport_h):
    h, w = frame.shape[:2]
    new_w = int(w / zoom_factor)
    new_h = int(h / zoom_factor)
    if new_w < 1 or new_h < 1:
        return frame
    cx = (w - new_w) // 2
    cy = (h - new_h) // 2
    crop = frame[cy:cy + new_h, cx:cx + new_w]
    zoomed = cv2.resize(crop, (w, h), interpolation=cv2.INTER_CUBIC)
    return zoomed
