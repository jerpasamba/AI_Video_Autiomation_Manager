import os
import sys
import json
import logging

from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QStatusBar, QApplication, QMessageBox,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from app.queue_manager import QueueManager, TaskType
from app.worker_pool import WorkerPool
from monitoring import Monitor
from ui.dashboard_tab import DashboardTab
from ui.manhwa_tab import ManhwaTab
from ui.shorts_tab import ShortsTab
from ui.queue_tab import QueueTab
from ui.upload_tab import UploadTab
from ui.upload_history_tab import UploadHistoryTab
from ui.settings_tab import SettingsTab
from ui.console_tab import ConsoleTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Video Manager")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)

        self._load_config()
        self._init_monitor()
        self._init_queue()
        self._init_runners()
        self._init_workers()
        self._init_ui()
        self._connect_signals()

        self._status_timer = QTimer()
        self._status_timer.timeout.connect(self._update_status)
        self._status_timer.start(2000)

        self._auto_looping = False
        self._auto_timer = QTimer()
        self._auto_timer.timeout.connect(self._auto_loop_tick)
        self._failed_manhwa_chapters = set()
        self._clean_stale_scripts()

        self.status_bar.showMessage("Ready")

    def _load_config(self):
        config_path = os.path.join(ROOT, "config.json")
        if os.path.exists(config_path):
            with open(config_path) as f:
                self.config = json.load(f)
        else:
            self.config = {}

    def save_config(self):
        config_path = os.path.join(ROOT, "config.json")
        with open(config_path, "w") as f:
            json.dump(self.config, f, indent=4)

    def _init_monitor(self):
        self.monitor = Monitor(self.config)

    def _init_queue(self):
        self.queue_manager = QueueManager(self.config, self)
        self.queue_manager.set_monitor(self.monitor)
        self.queue_manager.auto_refill_callback = self._on_generation_completed

    def _init_runners(self):
        self.project_runners = {}

        def _wrap(name, fn):
            def _progress_wrapper(pct, step=""):
                log = logging.getLogger(name)
                log.info(step or f"Progress {pct}%")
                progress_cb(pct, step)
            def _run(task, progress_cb):
                nonlocal _progress_wrapper
                log = logging.getLogger(name)
                log.info(f"Starting {task.title}")
                fn(task, _progress_wrapper)
                log.info(f"Completed {task.title}")
            return _run

        def run_manhwa(task, progress_cb):
            log = logging.getLogger("manhwa")
            from projects.manhwa_pipeline import generate_chapter
            chapter_num = task.params.get("chapter_num", 1)
            log.info(f"Generating Manhwa Chapter {chapter_num}")
            def cb(pct, step=""):
                log.info(step or f"Progress {pct}%")
                progress_cb(pct, step)
            generate_chapter(chapter_num, cb, self.config)
            log.info("Manhwa chapter generation complete")

        def run_anime_short(task, progress_cb):
            log = logging.getLogger("anime")
            from projects.anime_shorts_pipeline import generate_from_url, auto_search_generate
            url = task.params.get("url", "")
            def cb(pct, step=""):
                log.info(step or f"Progress {pct}%")
                progress_cb(pct, step)
            if url == "__auto__":
                log.info("Starting auto-search anime generation")
                auto_search_generate(self.config, cb)
            else:
                log.info(f"Generating anime short from: {url[:60]}")
                generate_from_url(url, cb, self.config)
            log.info("Anime short generation complete")

        def run_minecraft(task, progress_cb):
            log = logging.getLogger("minecraft")
            from projects.minecraft_pipeline import generate_minecraft_story
            prompt = task.params.get("prompt", "Tell me a story")
            log.info(f"Generating Minecraft story: {prompt[:60]}")
            def cb(pct, step=""):
                log.info(step or f"Progress {pct}%")
                progress_cb(pct, step)
            generate_minecraft_story(prompt, cb, self.config)
            log.info("Minecraft story generation complete")

        def run_upload(task, progress_cb):
            video_path = task.params.get("video_path", "")
            title = task.params.get("title", "Video")
            description = task.params.get("description", "")
            tags = task.params.get("tags", [])
            platform = task.params.get("platform", "youtube")
            if platform == "youtube":
                from upload.youtube_uploader import upload_video
                thumbnail_path = task.params.get("thumbnail_path")
                upload_video(video_path, title, description, tags, progress_cb, self.config, thumbnail_path=thumbnail_path)
            elif platform == "facebook":
                from upload.facebook_uploader import upload_reel
                thumbnail_path = task.params.get("thumbnail_path")
                upload_reel(video_path, title, description, progress_cb, self.config, thumbnail_path=thumbnail_path)

        self.project_runners["manhwa_chapter"] = run_manhwa
        self.project_runners["anime_short"] = run_anime_short
        self.project_runners["minecraft_story"] = run_minecraft
        self.project_runners["upload_video"] = run_upload

    def _init_workers(self):
        self.worker_pool = WorkerPool(
            self.queue_manager, self.project_runners, parent=self
        )
        for w in self.worker_pool.workers:
            if w.name == "manhwa":
                w.signals.failed.connect(self._on_manhwa_failed)
        self.worker_pool.start_all()

    def _init_ui(self):
        self.setStyleSheet(f"""
            QMainWindow {{ background: #11111b; }}
            QWidget {{ color: #cdd6f4; font-size: 13px; }}
            QTabWidget::pane {{ background: #11111b; border: none; }}
            QTabBar::tab {{
                background: #181825; color: #6c7086; padding: 10px 20px;
                border: none; border-bottom: 2px solid transparent;
                font-weight: bold; font-size: 12px;
            }}
            QTabBar::tab:selected {{
                background: #1e1e2e; color: #cdd6f4;
                border-bottom: 2px solid #89b4fa;
            }}
            QTabBar::tab:hover:!selected {{
                color: #a6adc8;
                border-bottom: 2px solid #45475a;
            }}
            QScrollBar:vertical {{
                background: #181825; width: 10px; border: none;
            }}
            QScrollBar::handle:vertical {{
                background: #45475a; min-height: 30px; border-radius: 5px;
            }}
            QScrollBar::handle:vertical:hover {{ background: #585b70; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QScrollBar:horizontal {{
                background: #181825; height: 10px; border: none;
            }}
            QScrollBar::handle:horizontal {{
                background: #45475a; min-width: 30px; border-radius: 5px;
            }}
            QScrollBar::handle:horizontal:hover {{ background: #585b70; }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
            QStatusBar {{ background: #181825; color: #6c7086; font-size: 12px; border-top: 1px solid #313244; }}
        """)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        self.dashboard_tab = DashboardTab(self.queue_manager, self.config, self)
        self.manhwa_tab = ManhwaTab(self.queue_manager, self.config)
        self.shorts_tab = ShortsTab(self.queue_manager, self.config)
        self.queue_tab = QueueTab(self.queue_manager, self.config)
        self.upload_tab = UploadTab(self.queue_manager, self.config)
        self.upload_history_tab = UploadHistoryTab(self.config)
        self.settings_tab = SettingsTab(self.config, self)

        self.tabs.addTab(self.dashboard_tab, "Dashboard")
        self.tabs.addTab(self.manhwa_tab, "Manhwa")
        self.tabs.addTab(self.shorts_tab, "Shorts")
        self.tabs.addTab(self.upload_tab, "Upload")
        self.tabs.addTab(self.upload_history_tab, "History")
        self.tabs.addTab(self.queue_tab, "Queue")
        self.tabs.addTab(self.settings_tab, "Settings")

        self.console_tab = ConsoleTab()
        self.tabs.addTab(self.console_tab, "Console")

        self.setCentralWidget(self.tabs)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

    def _connect_signals(self):
        self.queue_manager.queue_changed.connect(self._on_queue_changed)

    def _on_queue_changed(self):
        running = self.queue_manager.get_running_count()
        pending = self.queue_manager.get_pending_count()
        completed = self.queue_manager.get_completed_count()
        total = running + pending + completed
        self.status_bar.showMessage(
            f"Queue: {running} running | {pending} pending | {completed} completed | {total} total"
        )

    def _update_status(self):
        self.dashboard_tab.refresh()
        self.queue_tab.refresh_table()

    def _clean_stale_scripts(self):
        try:
            from projects.manhwa_pipeline import _resolve_path
            project_path = os.path.abspath(os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                self.config.get("manhwa_project_path", "projects/manhwa_engine")
            ))
            bible_path = os.path.join(project_path, "story_bible.json")
            if not os.path.exists(bible_path):
                return
            with open(bible_path, encoding="utf-8") as f:
                bible = json.load(f)
            bible_chapters = {c["number"]: c for c in bible.get("chapters", [])}
            for ch_num, ch_data in bible_chapters.items():
                if ch_data.get("scenes"):
                    continue
                out_dir = os.path.join(project_path, "output", "Final", f"ch{ch_num:02d}")
                script_path = os.path.join(out_dir, "script.json")
                if os.path.exists(script_path):
                    with open(script_path, encoding="utf-8") as f:
                        script = json.load(f)
                    if not script.get("scenes"):
                        os.remove(script_path)
                        logging.getLogger("manhwa").info(
                            "Cleaned stale 0-scene script for ch%02d", ch_num
                        )
        except Exception as e:
            logging.getLogger("manhwa").warning("Failed to clean stale scripts: %s", e)

    def _on_manhwa_failed(self, task, error):
        ch = task.params.get("chapter_num")
        if ch and "0 scenes" in str(error):
            self._failed_manhwa_chapters.add(ch)
            remaining = 100 - len(self._failed_manhwa_chapters)
            self.status_bar.showMessage(
                f"Manhwa Ch{ch}: bible has 0 scenes for this chapter, skipped"
            )

    def _load_full_description(self, video_path):
        ch_dir = os.path.dirname(video_path)
        meta_path = os.path.join(ch_dir, "youtube_meta.json")
        try:
            if os.path.isfile(meta_path):
                with open(meta_path, encoding="utf-8") as f:
                    meta = json.load(f)
                d = (meta.get("description") or "").strip()
                if d:
                    return d
        except Exception:
            pass
        desc_file = os.path.join(ch_dir, "youtube_description.txt")
        if os.path.isfile(desc_file):
            try:
                with open(desc_file, encoding="utf-8") as f:
                    return f.read().strip()
            except Exception:
                pass
        try:
            from upload.youtube_uploader import resolve_manhwa_metadata
            _, desc = resolve_manhwa_metadata(video_path, self.config)
            if desc:
                return desc
        except Exception:
            pass
        return ""

    def _load_youtube_title(self, video_path):
        ch_dir = os.path.dirname(video_path)
        meta_path = os.path.join(ch_dir, "youtube_meta.json")
        try:
            if os.path.isfile(meta_path):
                with open(meta_path, encoding="utf-8") as f:
                    meta = json.load(f)
                t = (meta.get("title") or "").strip()
                if t:
                    return t
        except Exception:
            pass

        desc_file = os.path.join(ch_dir, "youtube_description.txt")
        try:
            if os.path.isfile(desc_file):
                with open(desc_file, encoding="utf-8") as f:
                    txt = f.read()
                if "TITLE:" in txt:
                    after = txt.split("TITLE:", 1)[1]
                    line = after.strip().splitlines()[0].strip()
                    if line:
                        return line
                for ln in txt.splitlines():
                    ln = ln.strip()
                    if ln:
                        return ln
        except Exception:
            pass
        try:
            from upload.youtube_uploader import resolve_manhwa_metadata
            title, _ = resolve_manhwa_metadata(video_path, self.config)
            if title:
                return title
        except Exception:
            pass
        try:
            import re
            dn = os.path.basename(os.path.dirname(video_path))
            m = re.search(r"ch(\d+)", dn)
            if m:
                ch = int(m.group(1))
                bible_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                           self.config.get("manhwa_project_path", "projects/manhwa_engine"),
                                           "story_bible.json")
                if os.path.isfile(bible_path):
                    with open(bible_path, encoding="utf-8") as f:
                        bible = json.load(f)
                    series = bible.get("title", "Manhwa").strip()
                    ch_info = next((c for c in bible.get("chapters", []) if c.get("number") == ch), None)
                    ch_name = (ch_info.get("title") or "").strip() if ch_info else ""
                    if ch_name:
                        return f"{series} | Chapter {ch}: {ch_name} (Manhwa Motion Comic)"
                    return f"{series} | Chapter {ch} (Manhwa Motion Comic)"
        except Exception:
            pass
        return None

    def _already_uploaded(self, video_path, platform):
        return any(
            t.type == TaskType.UPLOAD_VIDEO
            and t.params.get("video_path") == video_path
            and t.params.get("platform") == platform
            and t.status == TaskStatus.COMPLETED
            for t in self.queue_manager.get_tasks()
        )

    def _on_generation_completed(self, task):
        from projects.manhwa_pipeline import get_all_chapters, get_chapter_status
        if self.config.get("auto_upload", False) and task.type != TaskType.UPLOAD_VIDEO:
            video_path = None
            title = ""
            description = ""
            if task.type == TaskType.MANHWA_CHAPTER:
                info = get_chapter_status(task.params.get("chapter_num", 1), self.config)
                if info.get("video_path"):
                    video_path = info["video_path"]
                    ch = task.params.get("chapter_num", "?")
                    title = self._load_youtube_title(video_path) or f"Manhwa Chapter {ch}"
                    description = self._load_full_description(video_path) or f"AI-generated Manhwa motion comic - Chapter {ch}"
            elif task.type == TaskType.ANIME_SHORT:
                from projects.anime_shorts_pipeline import get_generated_shorts
                shorts = get_generated_shorts(self.config)
                if shorts:
                    s = shorts[0]
                    video_path = s["path"]
                    title = s["title"]
                    description = self._load_full_description(video_path) or f"AI-generated anime short - {title}"
            elif task.type == TaskType.MINECRAFT_STORY:
                from projects.minecraft_pipeline import get_generated_stories
                stories = get_generated_stories(self.config)
                if stories:
                    s = stories[0]
                    video_path = s["path"]
                    title = s["title"]
                    description = self._load_full_description(video_path) or f"AI-generated Minecraft story - {title}"
            if video_path and os.path.exists(video_path):
                fb_config = self.config.get("facebook", {})
                if fb_config.get("upload_enabled", True) and not self._already_uploaded(video_path, "facebook"):
                    self.queue_manager.add_task(
                        TaskType.UPLOAD_VIDEO,
                        {
                            "video_path": video_path,
                            "title": title,
                            "description": description,
                            "tags": ["ai", "automated", "video"],
                            "platform": "facebook",
                        },
                        f"Upload to FB: {title[:30]}",
                    )
                yt_config = self.config.get("youtube", {})
                if yt_config.get("upload_enabled", False) and not self._already_uploaded(video_path, "youtube"):
                    self.queue_manager.add_task(
                        TaskType.UPLOAD_VIDEO,
                        {
                            "video_path": video_path,
                            "thumbnail_path": os.path.join(os.path.dirname(video_path), "thumbnail.jpg")
                            if os.path.exists(os.path.join(os.path.dirname(video_path), "thumbnail.jpg"))
                            else None,
                            "title": title,
                            "description": description,
                            "tags": yt_config.get("default_tags", ["ai", "automated", "video"]),
                            "platform": "youtube",
                        },
                        f"Upload to YT: {title[:30]}",
                    )

    @property
    def auto_looping(self):
        return self._auto_looping

    def toggle_auto_loop(self):
        if self._auto_looping:
            self._auto_timer.stop()
            self._auto_looping = False
            self.config["auto_loop_enabled"] = False
            self.status_bar.showMessage("Auto-loop stopped")
            self.dashboard_tab.update_auto_button()
        else:
            interval = self.config.get("auto_loop_interval_minutes", 5) * 60000
            self._auto_timer.setInterval(interval)
            self._auto_timer.start()
            self._auto_looping = True
            self.config["auto_loop_enabled"] = True
            self.status_bar.showMessage("Auto-loop running - generating every 5 min")
            self._auto_loop_tick()
            self.dashboard_tab.update_auto_button()

    def _auto_loop_tick(self):
        from projects.manhwa_pipeline import get_all_chapters
        from projects.anime_shorts_pipeline import get_generated_shorts
        existing_tasks = self.queue_manager.get_tasks()
        existing_types = [(t.type, t.params.get("chapter_num"), t.params.get("url"), t.params.get("prompt")) for t in existing_tasks if t.status.value in ("pending", "running")]
        def already_queued(ttype, **kw):
            for et, ch, url, prompt in existing_types:
                if et != ttype:
                    continue
                for k, v in kw.items():
                    if k == "chapter_num" and ch == v:
                        return True
                    if k == "url" and url == v:
                        return True
                    if k == "prompt" and prompt == v:
                        return True
            return False
        try:
            chapters = get_all_chapters(self.config)
            next_ch = next((
                c for c in chapters
                if not c["has_video"]
                and c["chapter"] not in self._failed_manhwa_chapters
            ), None)
            if next_ch and not already_queued(TaskType.MANHWA_CHAPTER, chapter_num=next_ch["chapter"]):
                self.queue_manager.add_task(
                    TaskType.MANHWA_CHAPTER,
                    {"chapter_num": next_ch["chapter"]},
                    f"Auto: Manhwa Chapter {next_ch['chapter']}",
                )
            elif not next_ch:
                remaining = [c for c in chapters if not c["has_video"]]
                if remaining:
                    self.status_bar.showMessage(
                        f"All {len(remaining)} remaining manhwa chapters exhausted "
                        f"(bible has 0 scenes for remaining chapters)"
                    )
        except Exception as e:
            self.status_bar.showMessage(f"Auto-loop manhwa error: {e}")
        try:
            if not already_queued(TaskType.ANIME_SHORT, url="__auto__"):
                self.queue_manager.add_task(
                    TaskType.ANIME_SHORT,
                    {"url": "__auto__"},
                    "Auto: Anime Short",
                )
        except Exception as e:
            self.status_bar.showMessage(f"Auto-loop anime error: {e}")
        try:
            if not already_queued(TaskType.MINECRAFT_STORY, prompt="__auto__"):
                self.queue_manager.add_task(
                    TaskType.MINECRAFT_STORY,
                    {"prompt": "Tell me a random epic adventure story for a YouTube short"},
                    "Auto: Minecraft Story",
                )
        except Exception as e:
            self.status_bar.showMessage(f"Auto-loop minecraft error: {e}")

    def closeEvent(self, event):
        self._auto_timer.stop()
        self.worker_pool.stop_all()
        self.console_tab.close_handler()
        self.save_config()
        event.accept()
