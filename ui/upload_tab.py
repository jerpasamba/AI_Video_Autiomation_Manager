import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QListWidget, QListWidgetItem,
    QFrame, QCheckBox, QGroupBox, QSplitter,
    QProgressBar, QMessageBox,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from app.queue_manager import TaskType
from ui.theme import COLORS, btn_style, card_style


class UploadTab(QWidget):
    def __init__(self, queue_manager, config, parent=None):
        super().__init__(parent)
        self.queue = queue_manager
        self.config = config

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

        upload_all_btn = QPushButton("Upload All Pending")
        upload_all_btn.setStyleSheet(btn_style(COLORS['accent_green'], COLORS['accent_green_hover']))
        upload_all_btn.clicked.connect(self._upload_all)
        header_layout.addWidget(upload_all_btn)

        layout.addLayout(header_layout)

        splitter = QSplitter(Qt.Orientation.Horizontal)

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
        pending_inner.addWidget(self.pending_list)

        refresh_videos_btn = QPushButton("Scan for Videos")
        refresh_videos_btn.setStyleSheet(btn_style(COLORS['bg_input'], COLORS['border'], COLORS['text_secondary']))
        refresh_videos_btn.clicked.connect(self._refresh_pending)
        pending_inner.addWidget(refresh_videos_btn)

        pending_group.setLayout(pending_inner)
        left_layout.addWidget(pending_group)
        left_widget.setLayout(left_layout)

        # --- Right: Destinations + Progress ---
        right_widget = QWidget()
        right_layout = QVBoxLayout()

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
        """)
        progress_layout.addWidget(self.upload_progress_list)
        progress_group.setLayout(progress_layout)
        right_layout.addWidget(progress_group)

        right_widget.setLayout(right_layout)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([500, 500])

        layout.addWidget(splitter)

        self.setLayout(layout)

        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self._refresh_upload_progress)
        self._refresh_timer.start(3000)

        self._refresh_pending()

    def _refresh_pending(self):
        self.pending_list.clear()

        from projects.manhwa_pipeline import get_all_chapters
        from projects.anime_shorts_pipeline import get_generated_shorts
        from projects.minecraft_pipeline import get_generated_stories

        try:
            chapters = get_all_chapters(self.config)
            for ch in chapters:
                if ch.get("video_path") and ch.get("has_video"):
                    already_queued = any(
                        t.type == TaskType.UPLOAD_VIDEO
                        and t.params.get("video_path") == ch["video_path"]
                        and t.status.value in ("pending", "running")
                        for t in self.queue.get_tasks()
                    )
                    if not already_queued:
                        item = QListWidgetItem(f"[Manhwa] Chapter {ch['chapter']}")
                        item.setData(Qt.ItemDataRole.UserRole, ch["video_path"])
                        self.pending_list.addItem(item)
        except Exception:
            pass

        try:
            shorts = get_generated_shorts(self.config)
            for s in shorts:
                already_queued = any(
                    t.type == TaskType.UPLOAD_VIDEO
                    and t.params.get("video_path") == s["path"]
                    and t.status.value in ("pending", "running")
                    for t in self.queue.get_tasks()
                )
                if not already_queued:
                    item = QListWidgetItem(f"[Anime] {s['title'][:40]}")
                    item.setData(Qt.ItemDataRole.UserRole, s["path"])
                    self.pending_list.addItem(item)
        except Exception:
            pass

        try:
            stories = get_generated_stories(self.config)
            for s in stories:
                already_queued = any(
                    t.type == TaskType.UPLOAD_VIDEO
                    and t.params.get("video_path") == s["path"]
                    and t.status.value in ("pending", "running")
                    for t in self.queue.get_tasks()
                )
                if not already_queued:
                    item = QListWidgetItem(f"[Story] {s['title'][:40]}")
                    item.setData(Qt.ItemDataRole.UserRole, s["path"])
                    self.pending_list.addItem(item)
        except Exception:
            pass

    def _refresh_upload_progress(self):
        upload_tasks = [t for t in self.queue.get_tasks() if t.type == TaskType.UPLOAD_VIDEO]
        self.upload_progress_list.clear()

        for t in upload_tasks[-20:]:
            platform = t.params.get("platform", "?")
            title = t.title[:40]
            status = t.status.value
            progress = t.progress
            item = QListWidgetItem(f"[{platform}] {title} - {status} ({progress}%)")
            self.upload_progress_list.addItem(item)

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
            title = os.path.basename(path).replace("_shorts.mp4", "").replace("_video.mp4", "").replace("_", " ").title()
            description = f"AI-generated video - {title}"
            tags = ["ai", "automated", "video"]

            self.queue.add_task(
                TaskType.UPLOAD_VIDEO,
                {
                    "video_path": path,
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
