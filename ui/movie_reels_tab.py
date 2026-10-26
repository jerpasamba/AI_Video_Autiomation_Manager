import json
import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QGroupBox,
    QListWidget, QListWidgetItem, QProgressBar,
)
from PyQt6.QtCore import Qt

from app.queue_manager import TaskType
from ui.theme import COLORS, input_style, btn_style, progress_bar_style, group_style


class MovieReelsTab(QWidget):
    def __init__(self, queue_manager, config, parent=None):
        super().__init__(parent)
        self.queue = queue_manager
        self.config = config

        layout = QVBoxLayout()
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        header = QLabel("Movie Reels")
        header.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {COLORS['text_primary']};")
        layout.addWidget(header)

        desc = QLabel(
            "Downloads clips from famous movies (Avengers, Spider-Man, Batman, etc.), "
            "adds background music, and converts to 9:16 vertical format."
        )
        desc.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        btn_layout = QHBoxLayout()
        get_btn = QPushButton("Get Movie Clip")
        get_btn.setStyleSheet(btn_style(COLORS['accent_red'], COLORS['accent_red_hover']))
        get_btn.clicked.connect(self._get_clip)
        btn_layout.addWidget(get_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setStyleSheet(progress_bar_style(COLORS['accent_red']))
        layout.addWidget(self.progress)

        self.status = QLabel("")
        self.status.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        layout.addWidget(self.status)

        recent_group = QGroupBox("Downloaded Clips")
        recent_group.setStyleSheet(group_style())
        recent_layout = QVBoxLayout()

        self.recent_list = QListWidget()
        self.recent_list.setStyleSheet(f"""
            QListWidget {{
                background: {COLORS['bg_medium']}; color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']}; border-radius: 6px;
            }}
            QListWidget::item {{ padding: 8px; }}
            QListWidget::item:selected {{ background: {COLORS['border']}; }}
        """)
        self.recent_list.itemClicked.connect(self._show_details)
        recent_layout.addWidget(self.recent_list)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setStyleSheet(btn_style(COLORS['bg_input'], COLORS['border'], COLORS['text_secondary']))
        refresh_btn.clicked.connect(self._refresh_recent)
        recent_layout.addWidget(refresh_btn)

        recent_group.setLayout(recent_layout)
        layout.addWidget(recent_group)

        detail_group = QGroupBox("Details")
        detail_group.setStyleSheet(group_style())
        detail_layout = QVBoxLayout()

        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setStyleSheet(input_style())
        self.detail_text.setPlaceholderText("Click a clip above for details...")
        detail_layout.addWidget(self.detail_text)

        detail_group.setLayout(detail_layout)
        layout.addWidget(detail_group)

        self.setLayout(layout)
        self._refresh_recent()

    def _get_clip(self):
        self.queue.add_task(
            TaskType.MOVIE_REEL,
            {"topic": "__auto__"},
            "Movie Clip",
        )

    def _refresh_recent(self):
        self.recent_list.clear()
        try:
            from projects.moviereels_pipeline import get_generated_reels
            reels = get_generated_reels(self.config)
            for r in reels[:20]:
                hook = r["hook"][:80] if r["hook"] else "No title"
                dur = r["duration_sec"]
                item = QListWidgetItem(
                    f"{hook}  ({dur:.0f}s, {r['size_mb']:.0f}MB)"
                )
                item.setData(Qt.ItemDataRole.UserRole, r["path"])
                self.recent_list.addItem(item)
        except Exception:
            pass

    def _show_details(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        if not path or not os.path.exists(path):
            return
        meta_file = os.path.splitext(path)[0] + "_meta.json"
        if not os.path.exists(meta_file):
            self.detail_text.setPlainText(f"Video file: {os.path.basename(path)}\n(no metadata)")
            return
        try:
            with open(meta_file, encoding="utf-8") as f:
                data = json.load(f)
            lines = [f"TITLE: {data.get('hook', 'N/A')}"]
            if data.get("source_url"):
                lines.append(f"SOURCE: {data['source_url']}")
            dur = data.get("estimated_duration_seconds", 0)
            if dur:
                lines.append(f"Duration: {dur:.0f}s")
            if data.get("music"):
                lines.append(f"Music: {data['music']}")
            self.detail_text.setPlainText("\n".join(lines))
        except Exception as e:
            self.detail_text.setPlainText(f"Error: {e}")
