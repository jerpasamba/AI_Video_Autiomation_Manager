import os
import logging

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QListWidget, QListWidgetItem,
    QFrame, QCheckBox, QGroupBox, QSplitter,
    QProgressBar, QMessageBox,
)
from PyQt6.QtCore import Qt, QTimer

from app.queue_manager import TaskType
from ui.theme import COLORS, btn_style, card_style

log = logging.getLogger("upload")


class UploadTab(QWidget):
    def __init__(self, queue_manager, config, parent=None):
        super().__init__(parent)
        self.queue = queue_manager
        self.config = config

        self._selected_path = None

        layout = QVBoxLayout()
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

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

        cancel_all_btn = QPushButton("Cancel All Uploads")
        cancel_all_btn.setStyleSheet(btn_style(COLORS['accent_red'], COLORS['accent_red_hover'], "white"))
        cancel_all_btn.clicked.connect(self._cancel_all_uploads)
        header_layout.addWidget(cancel_all_btn)

        upload_all_btn = QPushButton("Upload All Pending")
        upload_all_btn.setStyleSheet(btn_style(COLORS['accent_green'], COLORS['accent_green_hover']))
        upload_all_btn.clicked.connect(self._upload_all)
        header_layout.addWidget(upload_all_btn)

        layout.addLayout(header_layout)

        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- Left: Pending list ---
        left_widget = QWidget()
        left_layout = QVBoxLayout()

        pending_group = QGroupBox("Pending Uploads")
        pending_group.setStyleSheet(card_style() + "QGroupBox { margin-top: 12px; }")
        pending_inner = QVBoxLayout()

        self.pending_list = QListWidget()
        self.pending_list.setStyleSheet(f"""
            QListWidget {{
                background: {COLORS['bg_medium']}; color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']}; border-radius: 6px;
            }}
            QListWidget::item {{ padding: 10px; }}
            QListWidget::item:selected {{ background: {COLORS['border']}; }}
        """)
        self.pending_list.itemClicked.connect(self._on_pending_selected)
        self.pending_list.itemDoubleClicked.connect(self._preview_selected)
        pending_inner.addWidget(self.pending_list)

        refresh_videos_btn = QPushButton("Scan for Videos")
        refresh_videos_btn.setStyleSheet(btn_style(COLORS['bg_input'], COLORS['border'], COLORS['text_secondary']))
        refresh_videos_btn.clicked.connect(self._refresh_pending)
        pending_inner.addWidget(refresh_videos_btn)

        pending_group.setLayout(pending_inner)
        left_layout.addWidget(pending_group)
        left_widget.setLayout(left_layout)

        # --- Right: Preview + Destinations + Progress ---
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        right_layout.setSpacing(12)

        # Preview panel
        preview_group = QGroupBox("Preview")
        preview_group.setStyleSheet(card_style() + "QGroupBox { margin-top: 12px; }")
        preview_layout = QVBoxLayout()
        preview_layout.setSpacing(8)

        self.preview_path_label = QLabel("Select a video to preview")
        self.preview_path_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        self.preview_path_label.setWordWrap(True)
        preview_layout.addWidget(self.preview_path_label)

        self.open_ext_btn = QPushButton("Open in External Player")
        self.open_ext_btn.setEnabled(False)
        self.open_ext_btn.setStyleSheet(btn_style(COLORS['accent_blue'], COLORS['accent_blue_hover']))
        self.open_ext_btn.clicked.connect(self._open_external)
        preview_layout.addWidget(self.open_ext_btn)

        preview_group.setLayout(preview_layout)
        right_layout.addWidget(preview_group)

        # Destinations panel
        dest_group = QGroupBox("Destinations")
        dest_group.setStyleSheet(card_style() + "QGroupBox { margin-top: 12px; }")
        dest_layout = QVBoxLayout()
        dest_layout.setSpacing(12)

        fb_box = QFrame()
        fb_box.setFrameShape(QFrame.Shape.StyledPanel)
        fb_box.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['facebook']}15; border: 2px dashed {COLORS['facebook']};
                border-radius: 12px; padding: 24px;
            }}
        """)
        fb_layout = QVBoxLayout()
        fb_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fb_label = QLabel("Facebook Reels")
        fb_label.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {COLORS['facebook']};")
        fb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fb_layout.addWidget(fb_label)
        fb_upload_btn = QPushButton("Upload All to Facebook")
        fb_upload_btn.setStyleSheet(btn_style(COLORS['facebook'], COLORS['facebook_hover'], "white"))
        fb_upload_btn.clicked.connect(lambda: self._upload_to_platform("facebook"))
        fb_layout.addWidget(fb_upload_btn)
        fb_box.setLayout(fb_layout)
        dest_layout.addWidget(fb_box)

        yt_box = QFrame()
        yt_box.setFrameShape(QFrame.Shape.StyledPanel)
        yt_box.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['youtube']}15; border: 2px dashed {COLORS['youtube']};
                border-radius: 12px; padding: 24px;
            }}
        """)
        yt_layout = QVBoxLayout()
        yt_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        yt_label = QLabel("YouTube / Shorts")
        yt_label.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {COLORS['youtube']};")
        yt_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        yt_layout.addWidget(yt_label)
        yt_upload_btn = QPushButton("Upload All to YouTube")
        yt_upload_btn.setStyleSheet(btn_style(COLORS['youtube'], COLORS['youtube_hover'], "white"))
        yt_upload_btn.clicked.connect(lambda: self._upload_to_platform("youtube"))
        yt_layout.addWidget(yt_upload_btn)
        yt_box.setLayout(yt_layout)
        dest_layout.addWidget(yt_box)

        dest_group.setLayout(dest_layout)
        right_layout.addWidget(dest_group)

        progress_group = QGroupBox("Upload Progress")
        progress_group.setStyleSheet(card_style() + "QGroupBox { margin-top: 12px; }")
        progress_layout = QVBoxLayout()
        self.upload_progress_list = QListWidget()
        self.upload_progress_list.setStyleSheet(f"""
            QListWidget {{
                background: {COLORS['bg_medium']}; color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']}; border-radius: 6px;
            }}
            QListWidget::item {{ padding: 6px; font-size: 11px; }}
            QListWidget::item:hover {{ background: {COLORS['bg_input']}; }}
        """)
        self.upload_progress_list.itemDoubleClicked.connect(self._open_upload_link)
        progress_layout.addWidget(self.upload_progress_list)
        progress_group.setLayout(progress_layout)
        right_layout.addWidget(progress_group)

        right_widget.setLayout(right_layout)

        main_splitter.addWidget(left_widget)
        main_splitter.addWidget(right_widget)
        main_splitter.setSizes([400, 600])

        layout.addWidget(main_splitter)

        self.setLayout(layout)

        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self._refresh_upload_progress)
        self._refresh_timer.start(3000)

        self._pending_timer = QTimer()
        self._pending_timer.timeout.connect(self._refresh_pending)
        self._pending_timer.start(5000)

        self._refresh_pending()

    def _on_pending_selected(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path and os.path.exists(path):
            self.preview_path_label.setText(os.path.basename(path))
            self._selected_path = path
            self.open_ext_btn.setEnabled(True)

    def _preview_selected(self, item):
        self._on_pending_selected(item)

    def _open_external(self):
        if self._selected_path and os.path.exists(self._selected_path):
            os.startfile(self._selected_path)

    def _add_pending(self, label, video_path):
        if self._already_uploaded(video_path, "facebook") and self._already_uploaded(video_path, "youtube"):
            return
        already_queued = any(
            t.type == TaskType.UPLOAD_VIDEO
            and t.params.get("video_path") == video_path
            and t.status.value in ("pending", "running")
            for t in self.queue.get_tasks()
        )
        if not already_queued:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, video_path)
            self.pending_list.addItem(item)

    def _refresh_pending(self):
        try:
            self._do_refresh_pending()
        except Exception as e:
            log.warning("_refresh_pending error: %s", e)
            import traceback
            log.warning(traceback.format_exc())

    def _do_refresh_pending(self):
        self.pending_list.clear()
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # Manhwa - scan chXX/chapter_XX_video.mp4
        manhwa_root = os.path.join(project_root, "projects", "manhwa_engine", "output", "Final")
        if os.path.isdir(manhwa_root):
            for entry in sorted(os.listdir(manhwa_root)):
                if entry.startswith("ch") and os.path.isdir(os.path.join(manhwa_root, entry)):
                    ch_dir = os.path.join(manhwa_root, entry)
                    for f in os.listdir(ch_dir):
                        if f.endswith("_video.mp4") and not f.startswith("panel_") and not f.startswith("title_"):
                            video_path = os.path.join(ch_dir, f)
                            if os.path.getsize(video_path) > 1024:
                                label = "[Manhwa] Chapter {}".format(entry[2:].lstrip("0") or entry[2:])
                                self._add_pending(label, video_path)

        # Anime
        anime_root = os.path.join(project_root, "projects", "anime_engine", "output", "shorts")
        if os.path.isdir(anime_root):
            for f in sorted(os.listdir(anime_root)):
                if f.endswith("_shorts.mp4"):
                    video_path = os.path.join(anime_root, f)
                    if os.path.getsize(video_path) > 1024:
                        self._add_pending(f"[Anime] {f[:40]}", video_path)

        # Minecraft
        mc_root = os.path.join(project_root, "projects", "minecraft_engine", "output")
        if os.path.isdir(mc_root):
            for f in sorted(os.listdir(mc_root)):
                if f.endswith(".mp4") and "story_" in f:
                    video_path = os.path.join(mc_root, f)
                    if os.path.getsize(video_path) > 1024:
                        self._add_pending(f"[Minecraft] {f}", video_path)

    def _refresh_upload_progress(self):
        upload_tasks = [t for t in self.queue.get_tasks() if t.type == TaskType.UPLOAD_VIDEO]
        self.upload_progress_list.clear()

        for t in upload_tasks[-20:]:
            platform = t.params.get("platform", "?")
            title = t.title[:40]
            status = t.status.value
            progress = t.progress
            step = t.step_name or ""
            info = f"[{platform}] {title} - {status} ({progress}%)"
            if step:
                info += f" | {step[:60]}"
            item = QListWidgetItem(info)
            if status == "completed":
                url = None
                if platform == "facebook":
                    # Older runs wrote "post_id: <id>"; newer runs write "ID: <id>".
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
            self.upload_progress_list.addItem(item)

    def _load_full_description(self, video_path):
        ch_dir = os.path.dirname(video_path)
        desc_file = os.path.join(ch_dir, "youtube_description.txt")
        if os.path.isfile(desc_file):
            try:
                with open(desc_file, encoding="utf-8") as f:
                    return f.read().strip()
            except Exception:
                pass
        return ""

    def _already_uploaded(self, video_path, platform):
        return any(
            t.type == TaskType.UPLOAD_VIDEO
            and t.params.get("video_path") == video_path
            and t.params.get("platform") == platform
            and t.status.value == "completed"
            for t in self.queue.get_tasks()
        )

    def _cancel_all_uploads(self):
        for t in self.queue.get_tasks():
            if t.type == TaskType.UPLOAD_VIDEO and t.status.value in ("pending", "running"):
                self.queue.cancel_task(t.id)

    def _open_upload_link(self, item):
        url = item.data(Qt.ItemDataRole.UserRole)
        if url and url.startswith("http"):
            import webbrowser
            webbrowser.open(url)

    def _upload_to_platform(self, platform):
        videos = []
        for i in range(self.pending_list.count()):
            item = self.pending_list.item(i)
            path = item.data(Qt.ItemDataRole.UserRole)
            videos.append(path)

        if not videos:
            QMessageBox.information(self, "No Videos", "No pending videos to upload.")
            return

        for path in videos:
            if self._already_uploaded(path, platform):
                continue
            title = os.path.basename(path).replace("_shorts.mp4", "").replace("_video.mp4", "").replace("_", " ").title()
            description = self._load_full_description(path) or f"AI-generated video - {title}"
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
                    "platform": platform,
                },
                f"Upload to {platform}: {title[:30]}",
            )

        self._refresh_pending()

    def _upload_all(self):
        self._upload_to_platform("youtube")
        self._upload_to_platform("facebook")

    def _on_auto_upload_changed(self, state):
        self.config["auto_upload"] = state == Qt.CheckState.Checked.value
