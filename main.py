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


sys.excepthook = _global_excepthook

if __name__ == "__main__":
    _ensure_utf8_stdio()
    # Load .env so secrets (tokens/keys) don't need to live in config.json.
    load_dotenv()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
