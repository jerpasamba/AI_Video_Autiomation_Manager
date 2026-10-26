import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QTextEdit, QFrame,
    QGroupBox, QProgressBar, QCheckBox, QListWidget,
    QListWidgetItem, QDialog, QDialogButtonBox,
    QFormLayout, QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from app.queue_manager import TaskType
from ui.theme import COLORS, btn_style, input_style, card_style, progress_bar_style, group_style


def show_url_dialog(parent):
    dialog = QDialog(parent)
    dialog.setWindowTitle("Generate Anime Short")
    dialog.setMinimumWidth(500)
    dialog.setStyleSheet(f"background: {COLORS['bg_dark']}; color: {COLORS['text_primary']};")
    layout = QVBoxLayout()
    label = QLabel("Enter YouTube URL or search query:")
    label.setStyleSheet(f"color: {COLORS['text_primary']};")
    url_input = QLineEdit()
    url_input.setPlaceholderText("https://youtube.com/watch?v=... or search term")
    url_input.setStyleSheet(input_style())
    layout.addWidget(label)
    layout.addWidget(url_input)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    dialog.setLayout(layout)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return url_input.text().strip()
    return None


def show_prompt_dialog(parent):
    dialog = QDialog(parent)
    dialog.setWindowTitle("Generate Minecraft Story")
    dialog.setMinimumWidth(500)
    dialog.setStyleSheet(f"background: {COLORS['bg_dark']}; color: {COLORS['text_primary']};")
    layout = QVBoxLayout()
    label = QLabel("Enter a story prompt:")
    label.setStyleSheet(f"color: {COLORS['text_primary']};")
    prompt_input = QTextEdit()
    prompt_input.setPlaceholderText("e.g., A brave villager who discovers a hidden nether portal...")
    prompt_input.setMaximumHeight(120)
    prompt_input.setStyleSheet(input_style())
    layout.addWidget(label)
    layout.addWidget(prompt_input)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    dialog.setLayout(layout)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return prompt_input.toPlainText().strip()
    return None


class ShortsTab(QWidget):
    def __init__(self, queue_manager, config, parent=None):
        super().__init__(parent)
        self.queue = queue_manager
        self.config = config

        layout = QVBoxLayout()
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        header = QLabel("Shorts Generator")
        header.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {COLORS['text_primary']};")
        layout.addWidget(header)

        # --- Anime Group ---
        anime_group = QGroupBox("Anime Shorts")
        anime_group.setStyleSheet(group_style())
        anime_layout = QVBoxLayout()
        anime_layout.setSpacing(10)

        url_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("YouTube URL or search query...")
        self.url_input.setStyleSheet(input_style())
        url_layout.addWidget(self.url_input)

        gen_url_btn = QPushButton("Generate from URL")
        gen_url_btn.setStyleSheet(btn_style(COLORS['accent_blue'], COLORS['accent_blue_hover']))
        gen_url_btn.clicked.connect(self._generate_from_url)
        url_layout.addWidget(gen_url_btn)

        anime_layout.addLayout(url_layout)

        auto_layout = QHBoxLayout()
        self.auto_search_toggle = QCheckBox("Auto-Search & Generate Mode")
        self.auto_search_toggle.setStyleSheet(f"color: {COLORS['text_primary']};")
        auto_layout.addWidget(self.auto_search_toggle)

        auto_search_btn = QPushButton("Auto-Generate Now")
        auto_search_btn.setStyleSheet(btn_style(COLORS['accent_green'], COLORS['accent_green_hover']))
        auto_search_btn.clicked.connect(self._auto_generate)
        auto_layout.addWidget(auto_search_btn)

        auto_layout.addStretch()
        anime_layout.addLayout(auto_layout)

        self.anime_progress = QProgressBar()
        self.anime_progress.setVisible(False)
        self.anime_progress.setStyleSheet(progress_bar_style(COLORS['accent_blue']))
        anime_layout.addWidget(self.anime_progress)

        self.anime_status = QLabel("")
        self.anime_status.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        anime_layout.addWidget(self.anime_status)

        anime_group.setLayout(anime_layout)
        layout.addWidget(anime_group)

        # --- Minecraft Group ---
        minecraft_group = QGroupBox("Minecraft Stories")
        minecraft_group.setStyleSheet(group_style())
        mc_layout = QVBoxLayout()
        mc_layout.setSpacing(10)

        self.prompt_input = QTextEdit()
        self.prompt_input.setPlaceholderText("Enter a story prompt...\ne.g., A brave villager who discovers a hidden nether portal")
        self.prompt_input.setMaximumHeight(100)
        self.prompt_input.setStyleSheet(input_style())
        mc_layout.addWidget(self.prompt_input)

        mc_btn_layout = QHBoxLayout()
        gen_prompt_btn = QPushButton("Generate Story from Prompt")
        gen_prompt_btn.setStyleSheet(btn_style(COLORS['accent_purple'], COLORS['accent_purple_hover']))
        gen_prompt_btn.clicked.connect(self._generate_minecraft)
        mc_btn_layout.addWidget(gen_prompt_btn)

        random_btn = QPushButton("Random Story")
        random_btn.setStyleSheet(btn_style(COLORS['accent_yellow'], COLORS['accent_yellow_hover']))
        random_btn.clicked.connect(self._generate_random_minecraft)
        mc_btn_layout.addWidget(random_btn)

        mc_btn_layout.addStretch()
        mc_layout.addLayout(mc_btn_layout)

        self.mc_progress = QProgressBar()
        self.mc_progress.setVisible(False)
        self.mc_progress.setStyleSheet(progress_bar_style(COLORS['accent_purple']))
        mc_layout.addWidget(self.mc_progress)

        self.mc_status = QLabel("")
        self.mc_status.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        mc_layout.addWidget(self.mc_status)

        minecraft_group.setLayout(mc_layout)
        layout.addWidget(minecraft_group)

        # --- Recent Group ---
        recent_group = QGroupBox("Recently Generated")
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
        recent_layout.addWidget(self.recent_list)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setStyleSheet(btn_style(COLORS['bg_input'], COLORS['border'], COLORS['text_secondary']))
        refresh_btn.clicked.connect(self._refresh_recent)
        recent_layout.addWidget(refresh_btn)

        recent_group.setLayout(recent_layout)
        layout.addWidget(recent_group)

        self.setLayout(layout)

        self._refresh_recent()

    def _generate_from_url(self):
        url = self.url_input.text().strip()
        if url:
            self.queue.add_task(
                TaskType.ANIME_SHORT,
                {"url": url},
                f"Anime Short: {url[:40]}...",
            )
            self.url_input.clear()

    def _auto_generate(self):
        self.queue.add_task(
            TaskType.ANIME_SHORT,
            {"url": "__auto__"},
            "Auto-Search Anime Shorts",
        )

    def _generate_minecraft(self):
        prompt = self.prompt_input.toPlainText().strip()
        if prompt:
            self.queue.add_task(
                TaskType.MINECRAFT_STORY,
                {"prompt": prompt},
                f"Minecraft Story: {prompt[:40]}...",
            )
            self.prompt_input.clear()

    def _generate_random_minecraft(self):
        self.queue.add_task(
            TaskType.MINECRAFT_STORY,
            {"prompt": "Tell me a random epic adventure story for a YouTube short"},
            "Random Minecraft Story",
        )

    def _refresh_recent(self):
        self.recent_list.clear()

        from projects.anime_shorts_pipeline import get_generated_shorts
        from projects.minecraft_pipeline import get_generated_stories

        try:
            shorts = get_generated_shorts(self.config)
            for s in shorts[:10]:
                item = QListWidgetItem(f"[Anime] {s['title']} ({s['size_mb']:.0f}MB)")
                self.recent_list.addItem(item)
        except Exception:
            pass

        try:
            stories = get_generated_stories(self.config)
            for s in stories[:10]:
                item = QListWidgetItem(f"[Minecraft] {s['title']} ({s['size_mb']:.0f}MB)")
                self.recent_list.addItem(item)
        except Exception:
            pass
