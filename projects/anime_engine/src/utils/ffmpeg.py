import os
import subprocess
import shutil

from app.subprocess_utils import no_console_kwargs


def _find_ffmpeg():
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        ffprobe = shutil.which("ffprobe") or ffmpeg.replace("ffmpeg.exe", "ffprobe.exe").replace("ffmpeg", "ffprobe")
        return ffmpeg, ffprobe

    # Common paths
    for base in [
        os.environ.get("USERPROFILE", ""),
        os.environ.get("LOCALAPPDATA", ""),
        "C:\\Program Files",
        "C:\\",
    ]:
        for root, dirs, files in os.walk(base):
            if "ffmpeg.exe" in files:
                ffmpeg = os.path.join(root, "ffmpeg.exe")
                ffprobe = os.path.join(root, "ffprobe.exe")
                if not os.path.exists(ffprobe):
                    ffprobe = ffmpeg.replace("ffmpeg.exe", "ffprobe.exe")
                return ffmpeg, ffprobe
            if "ffmpeg" in dirs:
                continue

    raise RuntimeError("FFmpeg not found. Install: winget install ffmpeg")


FFMPEG, FFPROBE = _find_ffmpeg()


def run(cmd, **kwargs):
    kwargs = {**no_console_kwargs(), **kwargs}
    return subprocess.run(cmd, **kwargs)


def ffmpeg_cmd(args, **kwargs):
    kwargs = {**no_console_kwargs(), **kwargs}
    return subprocess.run([FFMPEG] + args, **kwargs)


def ffprobe_cmd(args, **kwargs):
    kwargs = {**no_console_kwargs(), **kwargs}
    return subprocess.run([FFPROBE] + args, **kwargs)
