import os
import subprocess


def no_console_kwargs():
    """Return subprocess kwargs that prevent a console window on Windows."""
    if os.name != "nt":
        return {}
    # CREATE_NO_WINDOW works for console executables (ffmpeg, yt-dlp, etc.)
    return {"creationflags": subprocess.CREATE_NO_WINDOW}
