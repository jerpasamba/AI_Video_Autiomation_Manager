import os
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QScrollArea,
    QGroupBox, QSizePolicy, QProgressBar,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from app.queue_manager import TaskType
from ui.theme import COLORS, btn_style, card_style, progress_bar_style, border_radius


class StatCard(QFrame):
    def __init__(self, title, value, color=COLORS["accent_blue"], parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(f"""
            StatCard {{
                background: {color}15;
                border: 1px solid {color}40;
                border-radius: 12px;
                padding: 16px;
            }}
        """)
        layout = QVBoxLayout()
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase;")
        self.value_label = QLabel(str(value))
        self.value_label.setStyleSheet(f"color: {color}; font-size: 28px; font-weight: bold;")
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        self.setLayout(layout)

    def set_value(self, value):
        self.value_label.setText(str(value))


class ProjectCard(QFrame):
    def __init__(self, title, status_text, action_text, action_color, action_callback, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(card_style())
        layout = QVBoxLayout()

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {COLORS['text_primary']};")
        layout.addWidget(title_lbl)

        self.status_lbl = QLabel(status_text)
        self.status_lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        layout.addWidget(self.status_lbl)

        layout.addSpacing(8)

        action_btn = QPushButton(action_text)
        action_btn.setStyleSheet(btn_style(action_color, action_color.replace("fa", "ec").replace("e1", "d5").replace("f7", "fe").replace("a1", "ac")))
        if action_callback:
            action_btn.clicked.connect(action_callback)
        layout.addWidget(action_btn)

        self.setLayout(layout)

    def set_status(self, text):
        self.status_lbl.setText(text)


class ActivityFeed(QFrame):
    def __init__(self, title="Recent Activity", parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(card_style())
        layout = QVBoxLayout()
        layout.setSpacing(4)

        header = QLabel(title)
        header.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {COLORS['text_primary']};")
        layout.addWidget(header)

        self.activity_list = QLabel("No activity yet")
        self.activity_list.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        self.activity_list.setWordWrap(True)
        layout.addWidget(self.activity_list)

        self.setLayout(layout)

    def set_activities(self, activities):
        if not activities:
            self.activity_list.setText("No activity yet")
        else:
            text = "<br>".join(activities[-10:])
            self.activity_list.setText(text)


class LiveMonitorPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(card_style())
        layout = QVBoxLayout()
        layout.setSpacing(10)

        header_layout = QHBoxLayout()
        header = QLabel("Live Monitor")
        header.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {COLORS['text_primary']};")
        header_layout.addWidget(header)
        layout.addLayout(header_layout)

        self.manhwa_row = QLabel("Manhwa: -- generated, -- failed")
        self.manhwa_row.setStyleSheet(f"color: {COLORS['accent_blue']}; font-size: 12px;")
        layout.addWidget(self.manhwa_row)

        self.anime_row = QLabel("Anime:  -- generated, -- failed")
        self.anime_row.setStyleSheet(f"color: {COLORS['accent_purple']}; font-size: 12px;")
        layout.addWidget(self.anime_row)

        self.minecraft_row = QLabel("Minecraft: -- generated, -- failed")
        self.minecraft_row.setStyleSheet(f"color: {COLORS['accent_peach']}; font-size: 12px;")
        layout.addWidget(self.minecraft_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {COLORS['border']};")
        layout.addWidget(sep)

        self.fb_row = QLabel("FB Uploads: -- ok, -- failed")
        self.fb_row.setStyleSheet(f"color: {COLORS['facebook']}; font-size: 12px;")
        layout.addWidget(self.fb_row)

        self.yt_row = QLabel("YT Uploads: -- ok, -- failed")
        self.yt_row.setStyleSheet(f"color: {COLORS['youtube']}; font-size: 12px;")
        layout.addWidget(self.yt_row)

        self.setLayout(layout)

    def update_stats(self, counters):
        gen = counters.get("generated", {})
        failed = counters.get("failed_generation", {})
        up = counters.get("uploaded", {})
        self.manhwa_row.setText(f"Manhwa: {gen.get('manhwa', 0)} generated, {failed.get('manhwa', 0)} failed")
        self.anime_row.setText(f"Anime:  {gen.get('anime', 0)} generated, {failed.get('anime', 0)} failed")
        self.minecraft_row.setText(f"Minecraft: {gen.get('minecraft', 0)} generated, {failed.get('minecraft', 0)} failed")
        fb = up.get("facebook", {})
        self.fb_row.setText(f"FB Uploads: {fb.get('ok', 0)} ok, {fb.get('fail', 0)} failed")
        yt = up.get("youtube", {})
        self.yt_row.setText(f"YT Uploads: {yt.get('ok', 0)} ok, {yt.get('fail', 0)} failed")


class DashboardTab(QWidget):
    def __init__(self, queue_manager, config, main_window=None):
        super().__init__()
        self.queue = queue_manager
        self.config = config
        self.main_window = main_window

        layout = QVBoxLayout()
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        header_layout = QHBoxLayout()
        header = QLabel("AI Video Manager")
        header.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {COLORS['text_primary']}; letter-spacing: 1px;")
        header_layout.addWidget(header)

        header_layout.addStretch()

        self.auto_btn = QPushButton(" START AUTO-GENERATION")
        self.auto_btn.setStyleSheet(self._auto_btn_style(False))
        if self.main_window:
            self.auto_btn.clicked.connect(self.main_window.toggle_auto_loop)
        header_layout.addWidget(self.auto_btn)

        layout.addLayout(header_layout)

        self.stats_grid = QGridLayout()
        self.stats_grid.setSpacing(12)

        self.card_videos = StatCard("Total Produced", "0", COLORS["accent_blue"])
        self.card_queue = StatCard("Queue Status", "0 pending", COLORS["accent_green"])
        self.card_today = StatCard("Today's Output", "0", COLORS["accent_yellow"])
        self.card_storage = StatCard("Storage Used", "0 MB", COLORS["accent_red"])

        self.stats_grid.addWidget(self.card_videos, 0, 0)
        self.stats_grid.addWidget(self.card_queue, 0, 1)
        self.stats_grid.addWidget(self.card_today, 0, 2)
        self.stats_grid.addWidget(self.card_storage, 0, 3)

        layout.addLayout(self.stats_grid)

        project_layout = QHBoxLayout()
        project_layout.setSpacing(12)

        self.manhwa_card = ProjectCard(
            "Manhwa Pipeline",
            "Checking status...",
            "Generate Next Chapter",
            COLORS["accent_blue"],
            self._on_generate_manhwa,
        )
        self.anime_card = ProjectCard(
            "Anime Shorts",
            "Checking status...",
            "Generate Next Short",
            COLORS["accent_purple"],
            self._on_generate_anime,
        )
        self.minecraft_card = ProjectCard(
            "Minecraft Stories",
            "Checking status...",
            "Generate Story",
            COLORS["accent_peach"],
            self._on_generate_minecraft,
        )

        project_layout.addWidget(self.manhwa_card)
        project_layout.addWidget(self.anime_card)
        project_layout.addWidget(self.minecraft_card)

        layout.addLayout(project_layout)

        monitor_layout = QHBoxLayout()
        monitor_layout.setSpacing(12)

        self.live_monitor = LiveMonitorPanel()
        monitor_layout.addWidget(self.live_monitor, 1)

        self.activity_feed = ActivityFeed(title="Live Activity")
        monitor_layout.addWidget(self.activity_feed, 1)

        layout.addLayout(monitor_layout)

        self.setLayout(layout)

        self.refresh()

    def _auto_btn_style(self, is_running):
        if is_running:
            return f"""
                QPushButton {{
                    background: {COLORS['accent_red']}; color: #1e1e2e;
                    border: none; border-radius: 8px;
                    padding: 12px 24px; font-size: 14px; font-weight: bold;
                }}
                QPushButton:hover {{ background: {COLORS['accent_red_hover']}; }}
            """
        return f"""
            QPushButton {{
                background: {COLORS['accent_green']}; color: #1e1e2e;
                border: none; border-radius: 8px;
                padding: 12px 24px; font-size: 14px; font-weight: bold;
            }}
            QPushButton:hover {{ background: {COLORS['accent_green_hover']}; }}
        """

    def update_auto_button(self):
        if not self.main_window:
            return
        running = self.main_window.auto_looping
        self.auto_btn.setText(" STOP AUTO-GENERATION" if running else " START AUTO-GENERATION")
        self.auto_btn.setStyleSheet(self._auto_btn_style(running))

    def refresh(self):
        tasks = self.queue.get_tasks()
        completed = [t for t in tasks if t.status.value == "completed"]
        pending = [t for t in tasks if t.status.value == "pending"]
        running = [t for t in tasks if t.status.value == "running"]

        self.card_videos.set_value(len(completed))
        self.card_queue.set_value(f"{len(pending)} pending / {len(running)} running")
        today_count = sum(1 for t in completed if t.completed_at and t.completed_at.startswith(datetime.now().strftime("%Y-%m-%d")))
        self.card_today.set_value(today_count)

        total_mb = 0
        for t in completed:
            vp = t.params.get("video_path", "")
            if vp and os.path.exists(vp):
                total_mb += os.path.getsize(vp) / (1024 * 1024)
        self.card_storage.set_value(f"{total_mb:.0f} MB")

        if self.queue.monitor:
            counters = self.queue.monitor.get_counters()
            self.live_monitor.update_stats(counters)
            activity = self.queue.monitor.get_activity(10)
            lines = []
            for a in activity:
                try:
                    t = a["time"].split("T")[1].split(".")[0][:5]
                except Exception:
                    t = "?"
                lines.append(f"[{t}] {a['text']}")
            self.activity_feed.set_activities(lines)

        from projects.manhwa_pipeline import get_all_chapters
        try:
            chapters = get_all_chapters(self.config)
            generated = sum(1 for c in chapters if c["has_video"])
            total = len(chapters)
            next_ch = next((c["chapter"] for c in chapters if not c["has_video"]), None)
            status = f"{generated}/{total} chapters done"
            if next_ch:
                status += f" | Next: Ch.{next_ch}"
            self.manhwa_card.set_status(status)
        except Exception as e:
            self.manhwa_card.set_status(f"Error: {e}")

        from projects.anime_shorts_pipeline import get_generated_shorts
        try:
            shorts = get_generated_shorts(self.config)
            self.anime_card.set_status(f"{len(shorts)} shorts generated")
        except Exception as e:
            self.anime_card.set_status(f"Error: {e}")

        from projects.minecraft_pipeline import get_generated_stories
        try:
            stories = get_generated_stories(self.config)
            self.minecraft_card.set_status(f"{len(stories)} stories generated")
        except Exception as e:
            self.minecraft_card.set_status(f"Error: {e}")

    def _on_generate_manhwa(self):
        from projects.manhwa_pipeline import get_all_chapters
        chapters = get_all_chapters(self.config)
        next_ch = next((c for c in chapters if not c["has_video"]), None)
        if next_ch:
            self.queue.add_task(
                TaskType.MANHWA_CHAPTER,
                {"chapter_num": next_ch["chapter"]},
                f"Generate Manhwa Chapter {next_ch['chapter']}",
            )

    def _on_generate_anime(self):
        from ui.shorts_tab import show_url_dialog
        url = show_url_dialog(self)
        if url:
            self.queue.add_task(
                TaskType.ANIME_SHORT,
                {"url": url},
                f"Anime Short: {url[:40]}...",
            )

    def _on_generate_minecraft(self):
        from ui.shorts_tab import show_prompt_dialog
        prompt = show_prompt_dialog(self)
        if prompt:
            self.queue.add_task(
                TaskType.MINECRAFT_STORY,
                {"prompt": prompt},
                f"Minecraft Story: {prompt[:40]}...",
            )
