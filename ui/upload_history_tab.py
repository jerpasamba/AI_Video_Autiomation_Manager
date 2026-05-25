import os
import logging
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QGroupBox, QMessageBox,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont

from ui.theme import COLORS, btn_style, card_style

log = logging.getLogger("upload_history")

PLATFORM_COLORS = {
    "youtube": QColor(COLORS["youtube"]),
    "youtube_short": QColor(COLORS["youtube"]),
    "facebook": QColor(COLORS["facebook"]),
}

PLATFORM_LABELS = {
    "youtube": "YouTube",
    "youtube_short": "YouTube Shorts",
    "facebook": "Facebook Reel",
}

TYPE_LABELS = {
    "youtube": "Video Upload",
    "youtube_short": "Short",
    "facebook": "Reel",
}


class UploadHistoryTab(QWidget):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config

        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        header_layout = QHBoxLayout()
        header = QLabel("Upload History")
        header.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {COLORS['text_primary']};")
        header_layout.addWidget(header)

        header_layout.addStretch()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setStyleSheet(btn_style(COLORS['bg_input'], COLORS['border'], COLORS['text_secondary']))
        refresh_btn.clicked.connect(self._load_history)
        header_layout.addWidget(refresh_btn)

        clear_btn = QPushButton("Clear All History")
        clear_btn.setStyleSheet(btn_style(COLORS['accent_red'], COLORS['accent_red_hover'], "white"))
        clear_btn.clicked.connect(self._clear_history)
        header_layout.addWidget(clear_btn)

        layout.addLayout(header_layout)

        stats_layout = QHBoxLayout()
        self.total_label = QLabel("Total: 0")
        self.total_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 13px;")
        stats_layout.addWidget(self.total_label)

        self.yt_label = QLabel("YouTube: 0")
        self.yt_label.setStyleSheet(f"color: {COLORS['youtube']}; font-size: 13px; font-weight: bold;")
        stats_layout.addWidget(self.yt_label)

        self.yt_short_label = QLabel("Shorts: 0")
        self.yt_short_label.setStyleSheet(f"color: {COLORS['youtube']}80; font-size: 13px;")
        stats_layout.addWidget(self.yt_short_label)

        self.fb_label = QLabel("Facebook: 0")
        self.fb_label.setStyleSheet(f"color: {COLORS['facebook']}; font-size: 13px; font-weight: bold;")
        stats_layout.addWidget(self.fb_label)

        stats_layout.addStretch()
        layout.addLayout(stats_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Date", "Video", "Platform", "Type", "Status", "URL"])
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background: {COLORS['bg_medium']}; color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']}; border-radius: 6px;
                gridline-color: {COLORS['border']};
                font-size: 12px;
            }}
            QTableWidget::item {{ padding: 6px; }}
            QTableWidget::item:selected {{ background: {COLORS['border']}; }}
            QHeaderView::section {{
                background: {COLORS['bg_card']}; color: {COLORS['text_secondary']};
                padding: 8px; border: 1px solid {COLORS['border']};
                font-weight: bold;
            }}
            QTableWidget::item:alternate {{
                background: {COLORS['bg_card']}80;
            }}
        """)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.itemDoubleClicked.connect(self._open_url)

        layout.addWidget(self.table)

        self.setLayout(layout)

        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self._load_history)
        self._refresh_timer.start(10000)

        self._load_history()

    def _load_history(self):
        from app import upload_registry
        try:
            registry = upload_registry.load_registry()
            items = registry.get("items", [])
        except Exception:
            items = []

        self.table.setRowCount(0)

        yt_count = 0
        yt_short_count = 0
        fb_count = 0

        for entry in reversed(items):
            row = self.table.rowCount()
            self.table.insertRow(row)

            platform = entry.get("platform", "unknown")
            platform_label = PLATFORM_LABELS.get(platform, platform)
            type_label = TYPE_LABELS.get(platform, "Unknown")

            ts = entry.get("uploaded_at", "")
            if ts:
                try:
                    dt = datetime.fromisoformat(ts)
                    date_str = dt.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    date_str = ts
            else:
                date_str = ""

            vpath = entry.get("path", "")
            video_name = os.path.basename(vpath) if vpath else "Unknown"
            remote_id = entry.get("remote_id", "")
            url = entry.get("url", "")
            status_text = "Uploaded" if remote_id else "Failed"

            if platform == "youtube":
                yt_count += 1
            elif platform == "youtube_short":
                yt_short_count += 1
            elif platform == "facebook":
                fb_count += 1

            self._set_item(row, 0, date_str)
            self._set_item(row, 1, video_name)

            platform_item = self._set_item(row, 2, platform_label)
            if platform.startswith("youtube"):
                platform_item.setForeground(PLATFORM_COLORS["youtube"])
            elif platform == "facebook":
                platform_item.setForeground(PLATFORM_COLORS["facebook"])

            self._set_item(row, 3, type_label)

            status_item = self._set_item(row, 4, status_text)
            if status_text == "Uploaded":
                status_item.setForeground(QColor(COLORS["status_success"]))
            else:
                status_item.setForeground(QColor(COLORS["status_fail"]))

            url_item = self._set_item(row, 5, url if url else "")
            if url:
                url_item.setForeground(QColor(COLORS["accent_blue"]))
                font = QFont()
                font.setUnderline(True)
                url_item.setFont(font)
                url_item.setToolTip(f"Open: {url}")

        total = yt_count + yt_short_count + fb_count
        self.total_label.setText(f"Total: {total}")
        self.yt_label.setText(f"YouTube: {yt_count}")
        self.yt_short_label.setText(f"Shorts: {yt_short_count}")
        self.fb_label.setText(f"Facebook: {fb_count}")

    def _set_item(self, row, col, text):
        item = QTableWidgetItem(str(text))
        self.table.setItem(row, col, item)
        return item

    def _open_url(self, item):
        row = item.row()
        url_item = self.table.item(row, 5)
        if url_item and url_item.text():
            import webbrowser
            webbrowser.open(url_item.text())

    def _clear_history(self):
        reply = QMessageBox.question(
            self, "Clear History",
            "Remove all upload history entries?\n(Videos on YouTube/Facebook will NOT be deleted.)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        from app import upload_registry
        registry = upload_registry.load_registry()
        registry["items"] = []
        upload_registry.save_registry(registry)
        self._load_history()
