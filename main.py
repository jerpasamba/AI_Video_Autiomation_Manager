import os
import sys
import traceback

from dotenv import load_dotenv

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, qInstallMessageHandler

from app.main_window import MainWindow


CRASH_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crash.log")


def _ensure_utf8_stdio():
    # Avoid Windows console UnicodeEncodeError (cp1252) when logs include emoji.
    for s in (sys.stdout, sys.stderr):
        try:
            if hasattr(s, "reconfigure"):
                s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _global_excepthook(exc_type, exc_value, exc_tb):
    msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    with open(CRASH_LOG, "a") as f:
        f.write(f"\n=== CRASH at {__import__('datetime').datetime.now()} ===\n{msg}\n")
    print(msg, file=sys.stderr)


def _ensure_ffmpeg_in_path():
    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        ffmpeg_dir = os.path.dirname(os.path.abspath(ffmpeg_exe))
        named_exe = os.path.join(ffmpeg_dir, "ffmpeg.exe")
        if not os.path.exists(named_exe):
            import shutil
            shutil.copy2(ffmpeg_exe, named_exe)
        scripts_dir = os.path.dirname(sys.executable)
        scripts_exe = os.path.join(scripts_dir, "ffmpeg.exe")
        if not os.path.exists(scripts_exe):
            import shutil
            shutil.copy2(ffmpeg_exe, scripts_exe)
        cur_path = os.environ.get("PATH", "")
        for p in (scripts_dir, ffmpeg_dir):
            if p not in cur_path:
                os.environ["PATH"] = p + os.pathsep + os.environ["PATH"]
    except Exception:
        pass


sys.excepthook = _global_excepthook

RELOAD_EXIT_CODE = 42

if __name__ == "__main__":
    _ensure_utf8_stdio()
    _ensure_ffmpeg_in_path()
    # Load .env so secrets (tokens/keys) don't need to live in config.json.
    load_dotenv()

    # Supervisor Mode: automatically re-runs the application if it exits with RELOAD_EXIT_CODE
    if os.environ.get("_APP_CHILD") != "1":
        import subprocess
        os.environ["_APP_CHILD"] = "1"
        while True:
            try:
                proc = subprocess.run([sys.executable] + sys.argv)
                if proc.returncode == RELOAD_EXIT_CODE:
                    print("\n[Live-Reload] ⚡ Restarting application with fresh code...\n")
                    continue
                sys.exit(proc.returncode)
            except KeyboardInterrupt:
                sys.exit(0)

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

