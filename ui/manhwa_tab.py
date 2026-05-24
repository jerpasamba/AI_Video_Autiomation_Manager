import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QScrollArea,
    QCheckBox, QProgressBar, QGroupBox,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QFont

from app.queue_manager import TaskType
from ui.theme import COLORS, btn_style, input_style, card_style, progress_bar_style, border_radius


class ChapterCard(QFrame):
    def __init__(self, info, generate_cb, upload_yt_cb, upload_fb_cb, parent=None):
        super().__init__(parent)
        self.info = info
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumHeight(180)

        status = info.get("status", "not_started")
        has_video = info.get("has_video", False)
        has_thumb = info.get("has_thumbnail", False)
        ch = info.get("chapter", "?")

        border_color = {
            "not_started": COLORS["text_dim"],
            "in_progress": COLORS["accent_yellow"],
            "generated": COLORS["accent_green"],
        }.get(status, COLORS["text_dim"])

        self.setStyleSheet(f"""
            ChapterCard {{
                background: {COLORS['bg_card']};
                border: 1px solid {border_color}60;
                border-radius: 10px;
                padding: 12px;
            }}
        """)

        layout = QHBoxLayout()
        layout.setSpacing(16)

        thumb_frame = QLabel()
        thumb_frame.setFixedSize(160, 90)
        thumb_frame.setStyleSheet(f"background: {COLORS['bg_medium']}; border-radius: 6px;")
        thumb_frame.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if has_thumb and info.get("thumbnail_path") and os.path.exists(info["thumbnail_path"]):
            pixmap = QPixmap(info["thumbnail_path"])
            thumb_frame.setPixmap(pixmap.scaled(160, 90, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            thumb_frame.setText(f"Ch.{ch}")
            thumb_frame.setStyleSheet(f"background: {COLORS['bg_medium']}; border-radius: 6px; color: {COLORS['text_dim']}; font-size: 18px;")

        layout.addWidget(thumb_frame)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)

        title_lbl = QLabel(f"Chapter {ch}")
        title_lbl.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {COLORS['text_primary']};")
        info_layout.addWidget(title_lbl)

        status_labels = {
            "not_started": "Not Started",
            "in_progress": "In Progress",
            "generated": "Generated",
        }
        status_colors = {
            "not_started": COLORS["text_muted"],
            "in_progress": COLORS["accent_yellow"],
            "generated": COLORS["accent_green"],
        }
        status_lbl = QLabel(f"\u25cf {status_labels.get(status, 'Unknown')}")
        status_lbl.setStyleSheet(f"color: {status_colors.get(status, COLORS['text_muted'])}; font-weight: 600;")
        info_layout.addWidget(status_lbl)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet(progress_bar_style())
        info_layout.addWidget(self.progress_bar)

        info_layout.addStretch()
        layout.addLayout(info_layout)

        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(6)

        self.gen_btn = QPushButton("Generate" if not has_video else "Regenerate")
        self.gen_btn.setStyleSheet(btn_style(COLORS['accent_blue'], COLORS['accent_blue_hover']))
        if generate_cb:
            self.gen_btn.clicked.connect(lambda checked, c=ch: generate_cb(c))
        btn_layout.addWidget(self.gen_btn)

        self.fb_btn = QPushButton("Facebook")
        self.fb_btn.setEnabled(has_video)
        self.fb_btn.setStyleSheet(btn_style(COLORS['facebook'], COLORS['facebook_hover'], "white"))
        if upload_fb_cb:
            self.fb_btn.clicked.connect(lambda checked, c=ch: upload_fb_cb(c))
        btn_layout.addWidget(self.fb_btn)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def update_status(self, info):
        self.info = info
        has_video = info.get("has_video", False)
        self.gen_btn.setText("Regenerate" if has_video else "Generate")
        self.fb_btn.setEnabled(has_video)

    def show_progress(self, visible=True):
        self.progress_bar.setVisible(visible)

    def set_progress(self, value):
        self.progress_bar.setValue(value)


class ManhwaTab(QWidget):
    def __init__(self, queue_manager, config, parent=None):
        super().__init__(parent)
        self.queue = queue_manager
        self.config = config
        self.cards = {}
        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self._refresh_cards)
        self._refresh_timer.start(3000)

        layout = QVBoxLayout()
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        header_layout = QHBoxLayout()
        header = QLabel("Manhwa Chapter Pipeline")
        header.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {COLORS['text_primary']};")
        header_layout.addWidget(header)

        header_layout.addStretch()

        self.auto_toggle = QCheckBox("Auto-Generate")
        self.auto_toggle.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 13px;")
        header_layout.addWidget(self.auto_toggle)

        gen_all_btn = QPushButton("Generate All Pending")
        gen_all_btn.setStyleSheet(btn_style(COLORS['accent_green'], COLORS['accent_green_hover']))
        gen_all_btn.clicked.connect(self._generate_all)
        header_layout.addWidget(gen_all_btn)

        layout.addLayout(header_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        self.chapters_widget = QWidget()
        self.chapters_layout = QGridLayout()
        self.chapters_layout.setSpacing(12)
        self.chapters_widget.setLayout(self.chapters_layout)

        scroll.setWidget(self.chapters_widget)
        layout.addWidget(scroll)

        self.setLayout(layout)

        self._load_chapters()

    def _load_chapters(self):
        from projects.manhwa_pipeline import get_all_chapters

        for widget in self.cards.values():
            widget.deleteLater()
        self.cards.clear()

        chapters = get_all_chapters(self.config)
        cols = 2

        for i, ch in enumerate(chapters):
            card = ChapterCard(
                ch,
                self._generate_chapter,
                self._upload_youtube,
                self._upload_facebook,
            )
            row = i // cols
            col = i % cols
            self.chapters_layout.addWidget(card, row, col)
            self.cards[ch["chapter"]] = card

    def _refresh_cards(self):
        from projects.manhwa_pipeline import get_all_chapters
        try:
            chapters = get_all_chapters(self.config)
            for ch in chapters:
                card = self.cards.get(ch["chapter"])
                if card:
                    card.update_status(ch)
                    tasks = self.queue.get_tasks()
                    running = [t for t in tasks if t.status.value == "running"
                               and t.params.get("chapter_num") == ch["chapter"]]
                    if running:
                        card.show_progress(True)
                        card.set_progress(running[0].progress)
                    else:
                        card.show_progress(False)
        except Exception:
            pass

    def _generate_chapter(self, chapter_num, flags=None):
        self.queue.add_task(
            TaskType.MANHWA_CHAPTER,
            {"chapter_num": chapter_num},
            f"Generate Manhwa Chapter {chapter_num}",
        )

    def _generate_all(self):
        from projects.manhwa_pipeline import get_all_chapters
        chapters = get_all_chapters(self.config)
        for ch in chapters:
            if not ch["has_video"]:
                self._generate_chapter(ch["chapter"])

    def _upload_youtube(self, chapter_num):
        from projects.manhwa_pipeline import get_chapter_status
        info = get_chapter_status(chapter_num, self.config)
        if info.get("video_path"):
            self.queue.add_task(
                TaskType.UPLOAD_VIDEO,
                {
                    "video_path": info["video_path"],
                    "title": f"Manhwa Chapter {chapter_num}",
                    "description": f"Manhwa motion comic - Chapter {chapter_num}",
                    "tags": ["manhwa", "motion comic", "webtoon"],
                    "platform": "youtube",
                },
                f"Upload Ch.{chapter_num} to YouTube",
            )

    def _upload_facebook(self, chapter_num):
        from projects.manhwa_pipeline import get_chapter_status
        info = get_chapter_status(chapter_num, self.config)
        if info.get("video_path"):
            self.queue.add_task(
                TaskType.UPLOAD_VIDEO,
                {
                    "video_path": info["video_path"],
                    "title": f"Manhwa Chapter {chapter_num}",
                    "description": "Manhwa motion comic",
                    "tags": [],
                    "platform": "facebook",
                },
                f"Upload Ch.{chapter_num} to Facebook",
            )
