import logging
import os
import sys
from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication

log = logging.getLogger("reloader")
RELOAD_EXIT_CODE = 42


class CodeReloader(QObject):
    """Watches Python source files and triggers automatic app reload upon code modifications."""
    reload_triggered = pyqtSignal(str)

    def __init__(self, root_dir=None, interval=1.0, parent=None):
        super().__init__(parent)
        self.root_dir = root_dir or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.interval = interval
        self._mtimes = {}
        self._running = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._check_files)
        self._watch_dirs = [
            os.path.join(self.root_dir, "app"),
            os.path.join(self.root_dir, "ui"),
            os.path.join(self.root_dir, "projects"),
            os.path.join(self.root_dir, "upload"),
            os.path.join(self.root_dir, "monitoring"),
        ]
        self._init_snapshot()

    def _init_snapshot(self):
        self._mtimes = self._scan_mtimes()

    def _scan_mtimes(self):
        mtimes = {}
        main_py = os.path.join(self.root_dir, "main.py")
        if os.path.exists(main_py):
            try:
                mtimes[main_py] = os.path.getmtime(main_py)
            except OSError:
                pass

        for d in self._watch_dirs:
            if not os.path.exists(d):
                continue
            for root, dirs, files in os.walk(d):
                dirs[:] = [
                    x for x in dirs
                    if x not in ("__pycache__", ".git", "venv", ".venv", "output", "assets")
                ]
                for f in files:
                    if f.endswith(".py"):
                        fp = os.path.join(root, f)
                        try:
                            mtimes[fp] = os.path.getmtime(fp)
                        except OSError:
                            pass
        return mtimes

    def start(self):
        if not self._running:
            self._running = True
            self._timer.start(int(self.interval * 1000))
            log.info("CodeReloader active. Watching %d Python files for live updates.", len(self._mtimes))

    def stop(self):
        self._running = False
        self._timer.stop()

    def _check_files(self):
        current = self._scan_mtimes()
        changed = []
        for fp, mtime in current.items():
            old_mtime = self._mtimes.get(fp)
            if old_mtime is not None and mtime > (old_mtime + 0.15):
                changed.append(fp)
            elif old_mtime is None and fp in current:
                changed.append(fp)

        if changed:
            self._mtimes = current
            rel = os.path.relpath(changed[0], self.root_dir)
            log.info("Code change detected in: %s. Reloading application...", rel)
            print(f"\n[Live-Reload] ⚡ Code change detected in {rel} -> Reloading application...\n")
            self._trigger_restart(rel)

    def _trigger_restart(self, changed_file):
        self.stop()
        app = QApplication.instance()
        if app:
            for widget in app.topLevelWidgets():
                try:
                    widget.close()
                except Exception:
                    pass
            if os.environ.get("_APP_CHILD") != "1":
                import subprocess
                cmd = [sys.executable] + sys.argv
                subprocess.Popen(cmd, cwd=self.root_dir)
            app.exit(RELOAD_EXIT_CODE)
