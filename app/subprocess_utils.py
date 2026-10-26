import os
import shutil
import subprocess
import sys


def _ensure_ffmpeg():
    """Ensure ffmpeg is in os.environ['PATH'] and ffmpeg.exe exists."""
    dirs_to_add = []
    # 1. Check venv Scripts
    if hasattr(sys, "prefix"):
        scripts_dir = os.path.join(sys.prefix, "Scripts")
        if os.path.isdir(scripts_dir):
            dirs_to_add.append(scripts_dir)

    # 2. Check imageio_ffmpeg
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.exists(exe):
            edir = os.path.dirname(exe)
            dirs_to_add.append(edir)
            dest = os.path.join(edir, "ffmpeg.exe")
            if not os.path.exists(dest):
                try:
                    shutil.copy2(exe, dest)
                except Exception:
                    pass
            # Also copy to venv Scripts if missing
            if hasattr(sys, "prefix"):
                venv_dest = os.path.join(sys.prefix, "Scripts", "ffmpeg.exe")
                if not os.path.exists(venv_dest):
                    try:
                        shutil.copy2(exe, venv_dest)
                    except Exception:
                        pass
    except Exception:
        pass

    current_path = os.environ.get("PATH", "")
    for d in dirs_to_add:
        if d not in current_path:
            os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")


_ensure_ffmpeg()


def get_ffmpeg_cmd():
    """Return the absolute path to ffmpeg.exe or 'ffmpeg' fallback."""
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        edir = os.path.dirname(exe)
        dest = os.path.join(edir, "ffmpeg.exe")
        if os.path.exists(dest):
            return dest
        return exe
    except Exception:
        return "ffmpeg"


def no_console_kwargs():
    """Return subprocess kwargs that prevent a console window on Windows."""
    if os.name != "nt":
        return {}
    # CREATE_NO_WINDOW works for console executables (ffmpeg, yt-dlp, etc.)
    return {"creationflags": subprocess.CREATE_NO_WINDOW}

