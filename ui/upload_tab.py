import os
import json
import logging

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QListWidget, QListWidgetItem,
    QFrame, QCheckBox, QGroupBox, QSplitter,
    QMessageBox,
)
from PyQt6.QtCore import Qt, QTimer

from app.queue_manager import TaskType
from ui.theme import COLORS, btn_style, card_style

log = logging.getLogger("upload")

PLATFORM_STYLES = {
    "facebook": {
        "accent": COLORS["facebook"],
        "accent_hover": COLORS["facebook_hover"],
        "label": "Facebook Reels",
        "short_label": "FB",
    },
    "youtube": {
        "accent": COLORS["youtube"],
        "accent_hover": COLORS["youtube_hover"],
        "label": "YouTube / Shorts",
        "short_label": "YT",
    },
}


class _PlatformPanel(QFrame):
    """Self-contained upload panel for one platform (facebook or youtube)."""

    def __init__(self, platform, queue, config, load_title_fn, load_desc_fn, parent=None):
        super().__init__(parent)
        self.platform = platform
        self.queue = queue
        self.config = config
        self._load_title_fn = load_title_fn
        self._load_desc_fn = load_desc_fn
        self._selected_path = None
        ps = PLATFORM_STYLES[platform]

        accent = ps["accent"]
        accent_hover = ps["accent_hover"]

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(f"""
            _PlatformPanel {{
                background: {accent}08;
                border: 1px solid {accent}40;
                border-radius: 10px;
            }}
        """)

        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        header = QLabel(ps["label"])
        header.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {accent};")
        layout.addWidget(header)

        pending_group = QGroupBox("Pending")
        pending_group.setStyleSheet(f"""
            QGroupBox {{
                background: {COLORS['bg_card']}; border: 1px solid {COLORS['border']};
                border-radius: 8px; padding: 12px; margin-top: 10px;
                font-size: 12px; color: {COLORS['text_muted']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin; subcontrol-position: top left;
                padding: 2px 8px;
            }}
        """)
        pending_inner = QVBoxLayout()
        pending_inner.setContentsMargins(0, 0, 0, 0)

        self.pending_list = QListWidget()
        self.pending_list.setStyleSheet(f"""
            QListWidget {{
                background: {COLORS['bg_medium']}; color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']}; border-radius: 6px;
            }}
            QListWidget::item {{ padding: 8px; font-size: 12px; }}
            QListWidget::item:selected {{ background: {accent}40; }}
        """)
        self.pending_list.itemClicked.connect(self._on_pending_selected)
        self.pending_list.itemDoubleClicked.connect(self._preview_selected)
        pending_inner.addWidget(self.pending_list)
        pending_group.setLayout(pending_inner)
        layout.addWidget(pending_group)

        progress_group = QGroupBox("Progress")
        progress_group.setStyleSheet(f"""
            QGroupBox {{
                background: {COLORS['bg_card']}; border: 1px solid {COLORS['border']};
                border-radius: 8px; padding: 12px; margin-top: 10px;
                font-size: 12px; color: {COLORS['text_muted']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin; subcontrol-position: top left;
                padding: 2px 8px;
            }}
        """)
        progress_inner = QVBoxLayout()
        progress_inner.setContentsMargins(0, 0, 0, 0)

        self.progress_list = QListWidget()
        self.progress_list.setStyleSheet(f"""
            QListWidget {{
                background: {COLORS['bg_medium']}; color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']}; border-radius: 6px;
            }}
            QListWidget::item {{ padding: 4px; font-size: 11px; }}
            QListWidget::item:hover {{ background: {COLORS['bg_input']}; }}
        """)
        self.progress_list.itemDoubleClicked.connect(self._open_upload_link)
        progress_inner.addWidget(self.progress_list)
        progress_group.setLayout(progress_inner)
        layout.addWidget(progress_group)

        self.upload_btn = QPushButton(f"Upload to {ps['short_label']}")
        self.upload_btn.setStyleSheet(btn_style(accent, accent_hover, "white"))
        self.upload_btn.clicked.connect(self._upload)
        layout.addWidget(self.upload_btn)

        layout.addStretch()
        self.setLayout(layout)

    def _on_pending_selected(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path and os.path.exists(path):
            self._selected_path = path

    def _preview_selected(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path and os.path.exists(path):
            os.startfile(path)

    def _open_upload_link(self, item):
        url = item.data(Qt.ItemDataRole.UserRole)
        if url and url.startswith("http"):
            import webbrowser
            webbrowser.open(url)

    def refresh_pending(self, videos):
        self.pending_list.clear()
        for label, vpath in videos:
            already = any(
                t.type == TaskType.UPLOAD_VIDEO
                and t.params.get("video_path") == vpath
                and t.params.get("platform") == self.platform
                and t.status.value == "completed"
                for t in self.queue.get_tasks()
            )
            already_running = any(
                t.type == TaskType.UPLOAD_VIDEO
                and t.params.get("video_path") == vpath
                and t.params.get("platform") == self.platform
                and t.status.value in ("pending", "running")
                for t in self.queue.get_tasks()
            )
            if already:
                continue
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, vpath)
            if already_running:
                item.setForeground(Qt.GlobalColor.gray)
            self.pending_list.addItem(item)

    def refresh_progress(self, tasks):
        self.progress_list.clear()
        platform_tasks = [t for t in tasks
                          if t.params.get("platform") == self.platform]
        for t in platform_tasks[-15:]:
            title = t.title[:35]
            status = t.status.value
            progress = t.progress
            step = t.step_name or ""
            err = getattr(t, "error", "") or ""
            info = f"{title} - {status} ({progress}%)"
            if step:
                info += f" | {step[:60]}"
            item = QListWidgetItem(info)
            if status == "failed" and err:
                short_err = err.strip().split("\n")[0][:80]
                item.setToolTip(f"Error: {short_err}")
                item.setForeground(Qt.GlobalColor.red)
            elif status == "completed":
                url = None
                if self.platform == "facebook":
                    if "post_id:" in step:
                        vid = step.split("post_id:")[-1].split(")")[0].strip()
                        url = f"https://www.facebook.com/reel/{vid}"
                    elif "ID:" in step:
                        vid = step.split("ID:")[-1].split()[0].strip()
                        url = f"https://www.facebook.com/reel/{vid}"
                else:
                    if "ID:" in step:
                        vid = step.split("ID:")[-1].split()[0].strip()
                        url = f"https://youtu.be/{vid}"
                if url:
                    item.setToolTip(f"Open in browser: {url}")
                    item.setData(Qt.ItemDataRole.UserRole, url)
            self.progress_list.addItem(item)

    def _upload(self):
        videos = []
        for i in range(self.pending_list.count()):
            item = self.pending_list.item(i)
            path = item.data(Qt.ItemDataRole.UserRole)
            videos.append(path)

        if not videos:
            QMessageBox.information(self, "No Videos",
                                    f"No pending videos to upload to {self.platform}.")
            return

        for path in videos:
            title = self._load_title_fn(path) or os.path.basename(path).replace(
                "_shorts.mp4", "").replace("_video.mp4", "").replace("_", " ").title()
            description = self._load_desc_fn(path) or f"AI-generated video - {title}"
            tags = ["ai", "automated", "video"]

            thumb_path = None
            cand = os.path.join(os.path.dirname(path), "thumbnail.jpg")
            if os.path.exists(cand):
                thumb_path = cand

            self.queue.add_task(
                TaskType.UPLOAD_VIDEO,
                {
                    "video_path": path,
                    "thumbnail_path": thumb_path,
                    "title": title,
                    "description": description,
                    "tags": tags,
                    "platform": self.platform,
                },
                f"Upload to {self.platform}: {title[:30]}",
            )


class UploadTab(QWidget):
    def __init__(self, queue_manager, config, parent=None):
        super().__init__(parent)
        self.queue = queue_manager
        self.config = config

        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        header_layout = QHBoxLayout()
        header = QLabel("Upload Manager")
        header.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {COLORS['text_primary']};")
        header_layout.addWidget(header)

        header_layout.addStretch()

        self.auto_upload_check = QCheckBox("Auto-Upload")
        self.auto_upload_check.setChecked(config.get("auto_upload", False))
        self.auto_upload_check.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 13px;")
        self.auto_upload_check.stateChanged.connect(self._on_auto_upload_changed)
        header_layout.addWidget(self.auto_upload_check)

        scan_btn = QPushButton("Scan for Videos")
        scan_btn.setStyleSheet(btn_style(COLORS['bg_input'], COLORS['border'], COLORS['text_secondary']))
        scan_btn.clicked.connect(self._refresh_pending)
        header_layout.addWidget(scan_btn)

        cancel_all_btn = QPushButton("Cancel All")
        cancel_all_btn.setStyleSheet(btn_style(COLORS['accent_red'], COLORS['accent_red_hover'], "white"))
        cancel_all_btn.clicked.connect(self._cancel_all_uploads)
        header_layout.addWidget(cancel_all_btn)

        reset_yt_btn = QPushButton("Reset YT History")
        reset_yt_btn.setStyleSheet(btn_style(COLORS['bg_input'], COLORS['border'], COLORS['text_secondary']))
        reset_yt_btn.clicked.connect(self._reset_youtube_history)
        header_layout.addWidget(reset_yt_btn)

        upload_all_btn = QPushButton("Upload All")
        upload_all_btn.setStyleSheet(btn_style(COLORS['accent_green'], COLORS['accent_green_hover']))
        upload_all_btn.clicked.connect(self._upload_all)
        header_layout.addWidget(upload_all_btn)

        layout.addLayout(header_layout)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.fb_panel = _PlatformPanel(
            "facebook", self.queue, self.config,
            self._load_youtube_title, self._load_full_description,
        )
        self.yt_panel = _PlatformPanel(
            "youtube", self.queue, self.config,
            self._load_youtube_title, self._load_full_description,
        )

        splitter.addWidget(self.fb_panel)
        splitter.addWidget(self.yt_panel)
        splitter.setSizes([500, 500])

        layout.addWidget(splitter)
        self.setLayout(layout)

        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self._refresh_upload_progress)
        self._refresh_timer.start(2500)

        self._pending_timer = QTimer()
        self._pending_timer.timeout.connect(self._refresh_pending)
        self._pending_timer.start(8000)

        self._refresh_pending()

    def _refresh_pending(self):
        try:
            self._do_refresh_pending()
        except Exception as e:
            log.warning("_refresh_pending error: %s", e)
            import traceback
            log.warning(traceback.format_exc())

    def _discover_videos(self):
        videos = []
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        manhwa_root = os.path.join(project_root, "projects", "manhwa_engine", "output", "Final")
        if os.path.isdir(manhwa_root):
            for entry in sorted(os.listdir(manhwa_root)):
                if entry.startswith("ch") and os.path.isdir(os.path.join(manhwa_root, entry)):
                    ch_dir = os.path.join(manhwa_root, entry)
                    for f in sorted(os.listdir(ch_dir)):
                        if f.endswith("_video.mp4") and not f.startswith("panel_") and not f.startswith("title_"):
                            vpath = os.path.join(ch_dir, f)
                            if os.path.getsize(vpath) > 1024:
                                label = "[Manhwa] Chapter {}".format(entry[2:].lstrip("0") or entry[2:])
                                videos.append((label, vpath))

        anime_root = os.path.join(project_root, "projects", "anime_engine", "output", "shorts")
        if os.path.isdir(anime_root):
            for f in sorted(os.listdir(anime_root)):
                if f.endswith("_shorts.mp4"):
                    vpath = os.path.join(anime_root, f)
                    if os.path.getsize(vpath) > 1024:
                        videos.append((f"[Anime] {f[:40]}", vpath))

        mc_root = os.path.join(project_root, "projects", "minecraft_engine", "output")
        if os.path.isdir(mc_root):
            for f in sorted(os.listdir(mc_root)):
                if f.endswith(".mp4") and "story_" in f:
                    vpath = os.path.join(mc_root, f)
                    if os.path.getsize(vpath) > 1024:
                        videos.append((f"[Minecraft] {f}", vpath))

        return videos

    def _do_refresh_pending(self):
        videos = self._discover_videos()
        self.fb_panel.refresh_pending(videos)
        self.yt_panel.refresh_pending(videos)

    def _refresh_upload_progress(self):
        tasks = self.queue.get_tasks()
        self.fb_panel.refresh_progress(tasks)
        self.yt_panel.refresh_progress(tasks)

    def _load_full_description(self, video_path):
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

        desc_path = os.path.join(ch_dir, "youtube_description.txt")
        try:
            if os.path.isfile(desc_path):
                with open(desc_path, encoding="utf-8") as f:
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
                project_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                             self.config.get("manhwa_project_path", "projects/manhwa_engine"))
                bible_path = os.path.join(project_path, "story_bible.json")
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

    def _cancel_all_uploads(self):
        for t in self.queue.get_tasks():
            if t.type == TaskType.UPLOAD_VIDEO and t.status.value in ("pending", "running"):
                self.queue.cancel_task(t.id)

    def _reset_youtube_history(self):
        from app import upload_registry
        for t in self.queue.get_tasks():
            if t.type == TaskType.UPLOAD_VIDEO and (t.params or {}).get("platform") in ("youtube", "youtube_short"):
                if t.status.value in ("pending", "running"):
                    self.queue.cancel_task(t.id)
        removed = self.queue.remove_tasks(
            lambda t: t.type == TaskType.UPLOAD_VIDEO and (t.params or {}).get("platform") in ("youtube", "youtube_short")
        )
        upload_registry.clear_platform("youtube")
        upload_registry.clear_platform("youtube_short")
        QMessageBox.information(self, "Reset", f"Cleared YouTube history ({removed} queue items).")
        self._refresh_pending()

    def _upload_all(self):
        self.yt_panel._upload()
        self.fb_panel._upload()

    def _on_auto_upload_changed(self, state):
        self.config["auto_upload"] = state == Qt.CheckState.Checked.value
