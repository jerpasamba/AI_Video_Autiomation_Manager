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

from app.queue_manager import QueueManager, TaskType, TaskStatus
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
from ui.movie_reels_tab import MovieReelsTab


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

        if self.config.get("auto_rescan_uploads_on_startup", False):
            QTimer.singleShot(1000, self._rescan_pending_uploads)
        if self.config.get("auto_sync_channel_enabled", True):
            QTimer.singleShot(3000, self._auto_sync_channel_background)

        if self.config.get("live_reload_enabled", True):
            try:
                from app.reloader import CodeReloader
                self.reloader = CodeReloader(parent=self)
                self.reloader.start()
                self.status_bar.showMessage("Ready (Live Reload Active ⚡)")
            except Exception as e:
                self.status_bar.showMessage("Ready")
        else:
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

        def run_moviereels(task, progress_cb):
            log = logging.getLogger("moviereels")
            from projects.moviereels_pipeline import generate_reel
            topic = task.params.get("topic", "__auto__")
            log.info(f"Generating MovieReels video: {topic[:60]}")
            def cb(pct, step=""):
                log.info(step or f"Progress {pct}%")
                progress_cb(pct, step)
            generate_reel(topic, cb, self.config)
            log.info("MovieReels generation complete")

        def run_upload(task, progress_cb):
            video_path = task.params.get("video_path", "")
            title = task.params.get("title", "Video")
            description = task.params.get("description", "")
            tags = task.params.get("tags", [])
            platform = task.params.get("platform", "youtube")
            thumbnail_path = task.params.get("thumbnail_path")
            if platform == "youtube":
                from upload.youtube_uploader import upload_video
                upload_video(video_path, title, description, tags, progress_cb, self.config, thumbnail_path=thumbnail_path)
            elif platform == "youtube_short":
                from upload.youtube_uploader import upload_short
                upload_short(video_path, title, description, tags, progress_cb, self.config, thumbnail_path=thumbnail_path)
            elif platform == "facebook":
                try:
                    from upload.facebook_uploader import upload_reel
                    upload_reel(video_path, title, description, progress_cb, self.config, thumbnail_path=thumbnail_path, tags=tags)
                except Exception as e:
                    if "code 190" in str(e) or "token invalid" in str(e).lower() or "application has been deleted" in str(e).lower():
                        progress_cb(15, "API restricted. Switching to Chrome Profile 1 automation...")
                        from upload.chrome_uploader import upload_facebook_reel_automated
                        upload_facebook_reel_automated(video_path, title, description, progress_cb, profile_name="Profile 1")
                    else:
                        raise
            elif platform == "tiktok":
                tt_cfg = self.config.get("tiktok", {})
                if tt_cfg.get("access_token"):
                    from upload.tiktok_uploader import upload_video as upload_tiktok
                    upload_tiktok(video_path, title, description, tags, progress_cb, self.config, thumbnail_path=thumbnail_path)
                else:
                    progress_cb(15, "Automating upload via Chrome Profile 1...")
                    from upload.chrome_uploader import upload_tiktok_automated
                    upload_tiktok_automated(video_path, title, description, tags, progress_cb, profile_name="Profile 1")

        self.project_runners["manhwa_chapter"] = run_manhwa
        self.project_runners["anime_short"] = run_anime_short
        self.project_runners["minecraft_story"] = run_minecraft
        self.project_runners["movie_reel"] = run_moviereels
        self.project_runners["reelforge"] = run_moviereels
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
        from ui.theme import main_stylesheet
        self.setStyleSheet(main_stylesheet())

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        self.dashboard_tab = DashboardTab(self.queue_manager, self.config, self)
        self.manhwa_tab = ManhwaTab(self.queue_manager, self.config)
        self.shorts_tab = ShortsTab(self.queue_manager, self.config)
        self.moviereels_tab = MovieReelsTab(self.queue_manager, self.config)
        self.queue_tab = QueueTab(self.queue_manager, self.config)
        self.upload_tab = UploadTab(self.queue_manager, self.config, main_window=self)
        self.upload_history_tab = UploadHistoryTab(self.config)
        self.settings_tab = SettingsTab(self.config, self)

        self.tabs.addTab(self.dashboard_tab, "Dashboard")
        self.tabs.addTab(self.manhwa_tab, "Manhwa")
        self.tabs.addTab(self.shorts_tab, "Shorts")
        self.tabs.addTab(self.moviereels_tab, "Movie Reels")
        self.tabs.addTab(self.upload_tab, "Upload")
        self.tabs.addTab(self.upload_history_tab, "Video Manager")
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

    def _load_meta_common(self, video_path):
        """Load metadata from any supported source."""
        ch_dir = os.path.dirname(video_path)

        # Minecraft metadata
        mc_meta = os.path.join(ch_dir, os.path.splitext(os.path.basename(video_path))[0] + "_meta.json")
        if os.path.isfile(mc_meta):
            try:
                with open(mc_meta, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

        # Manhwa youtube_meta.json
        meta_path = os.path.join(ch_dir, "youtube_meta.json")
        if os.path.isfile(meta_path):
            try:
                with open(meta_path, encoding="utf-8") as f:
                    meta = json.load(f)
                if meta.get("title") or meta.get("description"):
                    return meta
            except Exception:
                pass

        return None

    def _load_full_description(self, video_path):
        meta = self._load_meta_common(video_path)
        if meta and meta.get("description"):
            return meta["description"]

        ch_dir = os.path.dirname(video_path)
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
        meta = self._load_meta_common(video_path)
        if meta and meta.get("title"):
            return meta["title"]

        ch_dir = os.path.dirname(video_path)
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
        norm = os.path.normcase(os.path.normpath(video_path))
        # Check in-memory queue for completed, pending, or running upload tasks.
        if any(
            t.type == TaskType.UPLOAD_VIDEO
            and os.path.normcase(os.path.normpath(t.params.get("video_path", ""))) == norm
            and t.params.get("platform") == platform
            and t.status in (TaskStatus.COMPLETED, TaskStatus.PENDING, TaskStatus.RUNNING)
            for t in self.queue_manager.get_tasks()
        ):
            return True
        # Check persistent upload registry (survives restarts).
        try:
            from app import upload_registry
            existing = upload_registry.find_existing(video_path, platform=platform)
            if existing and existing.get("remote_id"):
                return True
        except Exception:
            pass
        # Cross-platform: if checking youtube_short, also check youtube (previously uploaded as regular)
        if platform == "youtube_short":
            try:
                existing = upload_registry.find_existing(video_path, platform="youtube")
                if existing and existing.get("remote_id"):
                    return True
            except Exception:
                pass
        return False

    def _queue_upload_manhwa(self, chapter_num):
        from projects.manhwa_pipeline import get_chapter_status
        info = get_chapter_status(chapter_num, self.config)
        video_path = info.get("video_path")
        if not video_path or not os.path.exists(video_path):
            return
        title = self._load_youtube_title(video_path) or f"Manhwa Chapter {chapter_num}"
        description = self._load_full_description(video_path) or f"AI-generated Manhwa motion comic - Chapter {chapter_num}"
        fb_tags = ["manhwa", "motion comic", "ai", "webtoon", "fantasy"]
        self._queue_upload_if_missing(video_path, title, description, fb_tags)

    def _queue_upload_if_missing(self, video_path, title, description, fb_tags):
        thumb_path = os.path.join(os.path.dirname(video_path), "thumbnail.jpg")
        if not os.path.exists(thumb_path):
            thumb_path = None
        fb_config = self.config.get("facebook", {})
        if fb_config.get("upload_enabled", True) and not self._already_uploaded(video_path, "facebook"):
            self.queue_manager.add_task(
                TaskType.UPLOAD_VIDEO,
                {
                    "video_path": video_path,
                    "thumbnail_path": thumb_path,
                    "title": title,
                    "description": description,
                    "tags": fb_tags,
                    "platform": "facebook",
                },
                f"Upload to FB: {title[:30]}",
            )
        yt_config = self.config.get("youtube", {})
        if yt_config.get("upload_enabled", False) and not self._already_uploaded(video_path, "youtube"):
            yt_tags = yt_config.get("default_tags", ["ai", "automated", "video"])
            self.queue_manager.add_task(
                TaskType.UPLOAD_VIDEO,
                {
                    "video_path": video_path,
                    "thumbnail_path": thumb_path,
                    "title": title,
                    "description": description,
                    "tags": yt_tags,
                    "platform": "youtube",
                },
                f"Upload to YT: {title[:30]}",
            )
        tt_config = self.config.get("tiktok", {})
        if tt_config.get("upload_enabled", False) and not self._already_uploaded(video_path, "tiktok"):
            self.queue_manager.add_task(
                TaskType.UPLOAD_VIDEO,
                {
                    "video_path": video_path,
                    "thumbnail_path": thumb_path,
                    "title": title,
                    "description": description,
                    "tags": fb_tags,
                    "platform": "tiktok",
                },
                f"Upload to TikTok: {title[:30]}",
            )

    def _queue_upload_minecraft(self, video_path, title, description, fb_tags):
        """Minecraft stories → YouTube Shorts + Facebook Reels (not regular YT video)."""
        thumb_path = os.path.join(os.path.dirname(video_path), "thumbnail.jpg")
        if not os.path.exists(thumb_path):
            thumb_path = None
        fb_config = self.config.get("facebook", {})
        if fb_config.get("upload_enabled", True) and not self._already_uploaded(video_path, "facebook"):
            self.queue_manager.add_task(
                TaskType.UPLOAD_VIDEO,
                {
                    "video_path": video_path,
                    "thumbnail_path": thumb_path,
                    "title": title,
                    "description": description,
                    "tags": fb_tags,
                    "platform": "facebook",
                },
                f"Upload to FB: {title[:30]}",
            )
        yt_config = self.config.get("youtube", {})
        already_yt = self._already_uploaded(video_path, "youtube")
        already_short = self._already_uploaded(video_path, "youtube_short")
        if yt_config.get("upload_enabled", False) and not already_yt and not already_short:
            yt_tags = yt_config.get("default_tags", ["ai", "automated", "video"])
            self.queue_manager.add_task(
                TaskType.UPLOAD_VIDEO,
                {
                    "video_path": video_path,
                    "thumbnail_path": thumb_path,
                    "title": title,
                    "description": description,
                    "tags": yt_tags,
                    "platform": "youtube_short",
                },
                f"Upload Short: {title[:30]}",
            )
        tt_config = self.config.get("tiktok", {})
        if tt_config.get("upload_enabled", False) and not self._already_uploaded(video_path, "tiktok"):
            self.queue_manager.add_task(
                TaskType.UPLOAD_VIDEO,
                {
                    "video_path": video_path,
                    "thumbnail_path": thumb_path,
                    "title": title,
                    "description": description,
                    "tags": fb_tags,
                    "platform": "tiktok",
                },
                f"Upload to TikTok: {title[:30]}",
            )

    def _on_generation_completed(self, task):
        log = logging.getLogger("main")
        try:
            if not self.config.get("auto_upload", False) or task.type == TaskType.UPLOAD_VIDEO:
                return
            video_path = None
            title = ""
            description = ""
            fb_tags = []
            if task.type == TaskType.MANHWA_CHAPTER:
                ch = task.params.get("chapter_num", 1)
                from projects.manhwa_pipeline import get_chapter_status
                info = get_chapter_status(ch, self.config)
                if info.get("video_path"):
                    video_path = info["video_path"]
                    title = self._load_youtube_title(video_path) or f"Manhwa Chapter {ch}"
                    description = self._load_full_description(video_path) or f"Manhwa Chapter {ch}"
                    fb_tags = ["manhwa", "motion comic", "ai", "webtoon", "fantasy"]
            elif task.type == TaskType.ANIME_SHORT:
                from projects.anime_shorts_pipeline import get_generated_shorts
                shorts = get_generated_shorts(self.config)
                if shorts:
                    s = shorts[0]
                    video_path = s["path"]
                    title = s["title"]
                    description = self._load_full_description(video_path) or s.get("description", f"Anime short - {title}")
                    fb_tags = s.get("tags", ["anime", "shorts", "highlight", "ai", "animeedit"])
            elif task.type == TaskType.MOVIE_REEL:
                from projects.moviereels_pipeline import get_generated_reels
                reels = get_generated_reels(self.config)
                if reels:
                    s = reels[0]
                    video_path = s["path"]
                    title = s.get("title") or s["hook"][:80] or "Movie Clip"
                    description = s.get("description") or f"Movie reel\n\n{s['hook']}"
                    fb_tags = s.get("tags") or ["movie", "reels", "facebook", "ai", "moviereels"]
            elif task.type == TaskType.MINECRAFT_STORY:
                from projects.minecraft_pipeline import get_generated_stories
                stories = get_generated_stories(self.config)
                if stories:
                    s = stories[0]
                    video_path = s["path"]
                    title = s.get("title") or s["title"]
                    description = s.get("description") or self._load_full_description(video_path) or title
                    fb_tags = s.get("tags", ["relationship", "true story", "heartbreak", "emotional", "reallife"])
            if video_path and os.path.exists(video_path):
                if task.type == TaskType.MINECRAFT_STORY:
                    self._queue_upload_minecraft(video_path, title, description, fb_tags)
                else:
                    self._queue_upload_if_missing(video_path, title, description, fb_tags)
        except Exception as e:
            log.error("Failed to queue auto-upload for %s: %s", task.title, e)

    def _rescan_pending_uploads(self):
        log = logging.getLogger("main")
        log.info("Scanning for generated content missing upload tasks...")
        queued = 0
        try:
            from projects.manhwa_pipeline import get_all_chapters
            for ch in get_all_chapters(self.config):
                if ch.get("has_video") and ch.get("video_path"):
                    info = ch
                    vp = info["video_path"]
                    title = self._load_youtube_title(vp) or f"Manhwa Chapter {info['chapter']}"
                    desc = self._load_full_description(vp) or title
                    self._queue_upload_if_missing(vp, title, desc, ["manhwa", "motion comic", "ai", "webtoon", "fantasy"])
                    queued += 1
        except Exception as e:
            log.warning("Manhwa rescan: %s", e)
        try:
            from projects.anime_shorts_pipeline import get_generated_shorts
            for s in get_generated_shorts(self.config):
                vp = s["path"]
                title = s["title"]
                desc = s.get("description") or title
                fb_tags = s.get("tags", ["anime", "shorts", "highlight", "ai", "animeedit"])
                self._queue_upload_if_missing(vp, title, desc, fb_tags)
                queued += 1
        except Exception as e:
            log.warning("Anime rescan: %s", e)
        try:
            from projects.minecraft_pipeline import get_generated_stories
            for s in get_generated_stories(self.config):
                vp = s["path"]
                title = s["title"]
                desc = s.get("description") or title
                fb_tags = s.get("tags", ["relationship", "true story", "heartbreak", "emotional", "reallife"])
                self._queue_upload_minecraft(vp, title, desc, fb_tags)
                queued += 1
        except Exception as e:
            log.warning("Minecraft rescan: %s", e)
        try:
            from projects.moviereels_pipeline import get_generated_reels
            for r in get_generated_reels(self.config):
                vp = r["path"]
                title = r.get("title") or r["hook"][:80] or "Movie Clip"
                desc = r.get("description") or f"Movie reel\n\n{r['hook']}"
                fb = r.get("tags") or ["movie", "reels", "facebook", "ai", "moviereels"]
                self._queue_upload_if_missing(vp, title, desc, fb)
                queued += 1
        except Exception as e:
            log.warning("MovieReels rescan: %s", e)
        if queued:
            self.status_bar.showMessage(f"Rescan: queued {queued} pending upload(s)")
        log.info("Rescan complete, queued %d upload(s)", queued)

    def _auto_sync_channel_background(self):
        handle = self.config.get("youtube_channel_handle", "@ZeroBalanceManhwa")
        if not handle:
            return
        clean_handle = handle.strip()
        if clean_handle.isdigit() or (clean_handle.startswith("@") and clean_handle[1:].isdigit()):
            log.warning("youtube_channel_handle was misconfigured with numeric ID %s; resetting to default @ZeroBalanceManhwa", handle)
            handle = "@ZeroBalanceManhwa"
            self.config["youtube_channel_handle"] = handle
        import threading
        def worker():
            try:
                from app.video_verifier import sync_channel_videos
                from app import upload_registry
                videos = sync_channel_videos(handle, platform="youtube", max_results=25, config=self.config)
                if not videos:
                    return
                reg = upload_registry.load_registry()
                existing_ids = {str(it.get("remote_id")).strip() for it in reg.get("items", []) if it.get("remote_id")}
                added = 0
                for v in videos:
                    rid = str(v["remote_id"]).strip()
                    if rid not in existing_ids:
                        v_metrics = {
                            "verified": True,
                            "status": "Verified Live",
                            "views": v.get("views") or 0,
                            "views_str": str(v.get("views")) if v.get("views") else "--",
                            "likes": 0,
                            "likes_str": "--",
                            "comments": 0,
                            "comments_str": "--",
                            "title": v.get("title", ""),
                            "url": v["url"],
                            "checked_at": datetime.now().isoformat(),
                            "error": None,
                        }
                        upload_registry.record_upload(
                            video_path=v["url"],
                            platform="youtube",
                            remote_id=rid,
                            url=v["url"],
                            metrics=v_metrics,
                        )
                        existing_ids.add(rid)
                        added += 1
                if added > 0:
                    logging.getLogger("main").info("Auto-synced %d new video(s) from channel %s", added, handle)
            except Exception as ex:
                logging.getLogger("main").debug("Auto-sync background check: %s", ex)

        threading.Thread(target=worker, daemon=True).start()


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
        existing_types = [(t.type, t.params.get("chapter_num"), t.params.get("url"), t.params.get("prompt"), t.params.get("topic")) for t in existing_tasks if t.status.value in ("pending", "running")]
        def already_queued(ttype, **kw):
            for et, ch, url, prompt, topic in existing_types:
                if et != ttype:
                    continue
                for k, v in kw.items():
                    if k == "chapter_num" and ch == v:
                        return True
                    if k == "url" and url == v:
                        return True
                    if k == "prompt" and prompt == v:
                        return True
                    if k == "topic" and topic == v:
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
                    {"prompt": "Write a short realistic story about a relationship problem or emotional struggle"},
                    "Auto: Real Story",
                )
        except Exception as e:
            self.status_bar.showMessage(f"Auto-loop minecraft error: {e}")
        try:
            if not already_queued(TaskType.MOVIE_REEL, topic="__auto__"):
                self.queue_manager.add_task(
                    TaskType.MOVIE_REEL,
                    {"topic": "__auto__"},
                    "Auto: Movie Clip",
                )
        except Exception as e:
            self.status_bar.showMessage(f"Auto-loop moviereels error: {e}")

    def closeEvent(self, event):
        self._auto_timer.stop()
        if hasattr(self, "reloader"):
            try:
                self.reloader.stop()
            except Exception:
                pass
        if hasattr(self, "upload_history_tab") and getattr(self.upload_history_tab, "_verifier_worker", None):
            try:
                if self.upload_history_tab._verifier_worker.isRunning():
                    self.upload_history_tab._verifier_worker.cancel()
                    self.upload_history_tab._verifier_worker.wait(2000)
            except Exception:
                pass
        self.worker_pool.stop_all()
        self.console_tab.close_handler()
        self.save_config()
        event.accept()
