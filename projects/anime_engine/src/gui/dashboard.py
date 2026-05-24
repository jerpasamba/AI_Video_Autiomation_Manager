import os
import json
import subprocess
import sys
import re
import traceback

from app.subprocess_utils import no_console_kwargs
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QListWidget, QListWidgetItem, QTextEdit, QLabel,
    QLineEdit, QProgressBar, QMessageBox, QGroupBox,
    QCheckBox, QComboBox, QGridLayout, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont


AUTO_SEARCH_QUERIES = [
    "attack on titan action scene",
    "demon slayer fight 4k",
    "jujutsu kaisen battle",
    "one piece fight scene",
    "naruto fight scene hd",
    "dragon ball fight scene",
    "chainsaw man action",
    "solo leveling scene",
]

BLOCKED_TITLE_WORDS = [
    "top 10", "top ten", "top 5", "top five",
    "compilation", "best of", "amv", "amv",
    "all fights", "all moments", "every fight",
    "ranked", "react", "reaction", "review",
    "opening 1", "ending 1", "op 1", "ed 1",
    "full episode", "episode 1",
]

DEFAULT_VIDEOS_PER_QUERY = 2
MAX_VIDEOS_TOTAL = 8


class AutoPipelineWorker(QThread):
    log = pyqtSignal(str)
    progress = pyqtSignal(int, int)
    count = pyqtSignal(int)
    finished = pyqtSignal(object)

    def __init__(self, pipeline, auto_upload=False, cleanup=False):
        super().__init__()
        self.pipeline = pipeline
        self.auto_upload = auto_upload
        self.cleanup = cleanup

    def run(self):
        from src.downloader.youtube import YouTubeDownloader

        self.log.emit("=== Auto Generate Mode ===")
        self.log.emit("Discovering trending anime content...")

        all_urls = set()
        for query in AUTO_SEARCH_QUERIES:
            try:
                cmd = [
                    sys.executable, "-m", "yt_dlp",
                    "--flat-playlist", "--dump-json",
                    "--playlist-end", str(DEFAULT_VIDEOS_PER_QUERY * 2),
                    "--no-download",
                    f"ytsearch{DEFAULT_VIDEOS_PER_QUERY * 2}:{query}"
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, **no_console_kwargs())
                if result.returncode == 0:
                    for line in result.stdout.strip().splitlines():
                        if line:
                            info = json.loads(line)
                            url = f"https://youtube.com/watch?v={info['id']}"
                            title = info.get("title", "Unknown")
                            duration = info.get("duration", 0)
                            title_lower = title.lower()
                            if any(w in title_lower for w in BLOCKED_TITLE_WORDS):
                                continue
                            if duration < 90 or duration > 1200:
                                continue
                            all_urls.add((url, title, duration))
            except Exception:
                pass
            if len(all_urls) >= MAX_VIDEOS_TOTAL:
                break

        urls = list(all_urls)[:MAX_VIDEOS_TOTAL]
        if not urls:
            self.log.emit("No videos found. Try again later.")
            self.finished.emit([])
            return

        self.log.emit(f"Found {len(urls)} videos to process")
        for _, title, dur in urls:
            mins = int(dur // 60)
            secs = int(dur % 60)
            self.log.emit(f"  {title[:60]} ({mins}:{secs:02d})")

        all_results = []
        for i, (url, title, _) in enumerate(urls):
            self.log.emit(f"\n--- Processing video {i+1}/{len(urls)} ---")
            self.progress.emit(i + 1, len(urls))
            try:
                results = self.pipeline.process_url(url, progress_callback=self.log.emit)
                all_results.extend(results)
                self.count.emit(len(all_results))
            except Exception as e:
                self.log.emit(f"❌ Error: {e}")
                self.log.emit(traceback.format_exc())

        self.log.emit(f"\n=== ✅ DONE! Generated {len(all_results)} shorts total ===")
        self.finished.emit(all_results)


class DashboardTab(QWidget):
    def __init__(self, pipeline):
        super().__init__()
        self.pipeline = pipeline
        self.generated_count = 0
        self.results = []
        self.setup_ui()
        self.check_music()

    def check_music(self):
        music_dir = "assets/music"
        if os.path.exists(music_dir):
            tracks = [f for f in os.listdir(music_dir)
                      if f.lower().endswith(('.mp3', '.wav', '.m4a', '.ogg'))]
            if not tracks:
                self.log_output.append("No BGM tracks found — click 'YouTube BGM' to download")

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        stats_layout = QHBoxLayout()
        self.count_label = QLabel("0 shorts generated")
        self.count_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #FFD700;")
        stats_layout.addWidget(self.count_label)
        stats_layout.addStretch()
        layout.addLayout(stats_layout)

        auto_group = QFrame()
        auto_group.setStyleSheet("QFrame { background: #1a1a2e; border-radius: 12px; padding: 16px; }")
        auto_layout = QVBoxLayout(auto_group)

        self.auto_btn = QPushButton(" AUTO GENERATE SHORTS")
        self.auto_btn.setMinimumHeight(80)
        self.auto_btn.setStyleSheet("""
            QPushButton {
                font-size: 28px; font-weight: bold;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #ff6b35, stop:1 #f7c731);
                color: #1a1a2e; border-radius: 12px; padding: 16px;
            }
            QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #ff8255, stop:1 #f7d851); }
            QPushButton:disabled { background: #444; color: #888; }
        """)
        self.auto_btn.clicked.connect(self.auto_generate)
        auto_layout.addWidget(self.auto_btn)

        auto_sub_layout = QHBoxLayout()
        self.cleanup_cb = QCheckBox(" Delete temp files after done")
        self.cleanup_cb.setChecked(True)
        self.cleanup_cb.setStyleSheet("color: #aaa; font-size: 12px;")

        self.bgm_dl_btn = QPushButton(" Download BGM")
        self.bgm_dl_btn.clicked.connect(self.download_bgm)
        self.bgm_dl_btn.setStyleSheet("font-size: 12px;")

        self.bgm_playlist_input = QLineEdit()
        bgm_url = self.pipeline.config.get("bgm_playlist_url", "")
        self.bgm_playlist_input.setText(bgm_url)
        self.bgm_playlist_input.setPlaceholderText("Paste your phonk/funk playlist URL...")
        self.bgm_playlist_input.setStyleSheet("font-size: 11px; padding: 4px;")

        auto_sub_layout.addWidget(self.bgm_dl_btn)
        auto_sub_layout.addWidget(self.bgm_playlist_input, 1)
        auto_sub_layout.addStretch()
        auto_sub_layout.addWidget(self.cleanup_cb)
        auto_layout.addLayout(auto_sub_layout)

        layout.addWidget(auto_group)

        progress_layout = QHBoxLayout()
        self.video_progress = QProgressBar()
        self.video_progress.setFormat("Video %v of %m")
        self.video_progress.setMinimumHeight(24)
        self.video_progress.setStyleSheet("""
            QProgressBar { border: 1px solid #555; border-radius: 6px; text-align: center; font-size: 13px; }
            QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #ff6b35, stop:1 #f7c731); border-radius: 6px; }
        """)
        progress_layout.addWidget(self.video_progress)
        self.clip_count_label = QLabel(" 0 clips")
        self.clip_count_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #4CAF50;")
        progress_layout.addWidget(self.clip_count_label)
        layout.addLayout(progress_layout)

        manual_toggle = QPushButton("+ Add specific URL (optional)")
        manual_toggle.setCheckable(True)
        manual_toggle.setStyleSheet("font-size: 11px; color: #aaa;")
        manual_toggle.toggled.connect(lambda checked: self.manual_group.setVisible(checked))
        layout.addWidget(manual_toggle)

        self.manual_group = QWidget()
        self.manual_group.setVisible(False)
        manual_layout = QHBoxLayout(self.manual_group)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("YouTube video or channel URL...")
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self.add_url)
        manual_layout.addWidget(self.url_input)
        manual_layout.addWidget(add_btn)
        self.queue_list = QListWidget()
        self.queue_list.setMaximumHeight(80)
        manual_layout.addWidget(self.queue_list, 1)
        layout.addWidget(self.manual_group)

        # ---- Results table ----
        results_label = QLabel("Generated Shorts:")
        results_label.setStyleSheet("font-weight: bold; color: #aaa; font-size: 13px;")
        layout.addWidget(results_label)

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(5)
        self.results_table.setHorizontalHeaderLabels(["#", "File", "Size", "Upload", "Delete"])
        self.results_table.horizontalHeader().setStretchLastSection(False)
        self.results_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.results_table.setColumnWidth(0, 30)
        self.results_table.setColumnWidth(2, 70)
        self.results_table.setColumnWidth(3, 80)
        self.results_table.setColumnWidth(4, 80)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.setMaximumHeight(200)
        self.results_table.setStyleSheet("""
            QTableWidget { background: #0d0d1a; color: #e0e0e0; font-size: 12px; }
            QHeaderView::section { background: #1a1a2e; color: #aaa; }
        """)
        layout.addWidget(self.results_table)

        # ---- Log ----
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(150)
        self.log_output.setStyleSheet("""
            QTextEdit { background: #0d0d1a; color: #e0e0e0; font-family: Consolas; font-size: 12px; }
        """)
        layout.addWidget(QLabel("Progress Log:"))
        layout.addWidget(self.log_output)

    def add_url(self):
        url = self.url_input.text().strip()
        if url:
            items = [self.queue_list.item(i).text() for i in range(self.queue_list.count())]
            if url not in items:
                self.queue_list.addItem(url)
                self.url_input.clear()

    def download_bgm(self):
        self.bgm_dl_btn.setEnabled(False)
        self.bgm_dl_btn.setText(" Downloading...")
        from src.utils.bgm_downloader import YouTubeBGMDownloader
        try:
            playlist_url = self.bgm_playlist_input.text().strip()
            if playlist_url:
                self.pipeline.config["bgm_playlist_url"] = playlist_url
                self.pipeline.config.save()
            dl = YouTubeBGMDownloader(playlist_url=playlist_url)
            tracks = dl.download_tracks(count=10, progress_callback=self.log_output.append)
            self.log_output.append(f"Downloaded {len(tracks)} BGM tracks from YouTube!")
        except Exception as e:
            import traceback
            self.log_output.append(f"BGM download failed: {e}")
            self.log_output.append(traceback.format_exc())
        self.bgm_dl_btn.setText(" Download BGM")
        self.bgm_dl_btn.setEnabled(True)

    def auto_generate(self):
        self.auto_btn.setEnabled(False)
        self.auto_btn.setText(" Generating...")
        self.log_output.clear()
        self.generated_count = 0
        self.count_label.setText("0 shorts generated")
        self.clip_count_label.setText(" 0 clips")
        self.results_table.setRowCount(0)
        self.results = []

        manual_urls = [self.queue_list.item(i).text() for i in range(self.queue_list.count())]

        self.w = AutoPipelineWorker(
            self.pipeline,
            auto_upload=False,
            cleanup=self.cleanup_cb.isChecked()
        )
        self.w.log.connect(self.log_output.append)
        self.w.progress.connect(lambda v, t: (self.video_progress.setMaximum(t), self.video_progress.setValue(v)))
        self.w.count.connect(lambda c: (setattr(self, 'generated_count', c),
                                         self.count_label.setText(f"{c} shorts generated"),
                                         self.clip_count_label.setText(f" {c} clips")))
        self.w.finished.connect(self.on_finished)
        self.w.start()

    def on_finished(self, results):
        self.auto_btn.setEnabled(True)
        self.auto_btn.setText(" AUTO GENERATE SHORTS")
        self.count_label.setText(f"{len(results)} shorts generated")
        self.video_progress.setValue(0)
        self.results = results

        self.results_table.setRowCount(len(results))
        for i, clip in enumerate(results):
            item_num = QTableWidgetItem(str(i + 1))
            item_num.setFlags(item_num.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.results_table.setItem(i, 0, item_num)

            item_file = QTableWidgetItem(os.path.basename(clip["path"]))
            item_file.setFlags(item_file.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.results_table.setItem(i, 1, item_file)

            size_mb = os.path.getsize(clip["path"]) / (1024 * 1024)
            item_size = QTableWidgetItem(f"{size_mb:.1f}MB")
            item_size.setFlags(item_size.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.results_table.setItem(i, 2, item_size)

            upload_btn = QPushButton("Upload")
            upload_btn.setStyleSheet("font-size: 11px;")
            has_secret = bool(self.pipeline.config["youtube"].get("client_secret_file"))
            upload_btn.setEnabled(has_secret)
            upload_btn.clicked.connect(lambda checked, idx=i: self.upload_single(idx))
            self.results_table.setCellWidget(i, 3, upload_btn)

            delete_btn = QPushButton("Delete")
            delete_btn.setStyleSheet("font-size: 11px; color: #ff6b6b;")
            delete_btn.clicked.connect(lambda checked, idx=i: self.delete_single(idx))
            self.results_table.setCellWidget(i, 4, delete_btn)

    def upload_single(self, idx):
        if idx >= len(self.results):
            return
        clip = self.results[idx]
        self.log_output.append(f"Uploading: {os.path.basename(clip['path'])}...")
        try:
            self.pipeline.upload_clip(clip, progress_callback=self.log_output.append)
            self.log_output.append(f"Uploaded and deleted: {os.path.basename(clip['path'])}")
            self.results_table.removeRow(idx)
            self.results.pop(idx)
        except Exception as e:
            self.log_output.append(f"Upload failed: {e}")
            self.log_output.append(traceback.format_exc())

    def delete_single(self, idx):
        if idx >= len(self.results):
            return
        clip = self.results[idx]
        try:
            if os.path.exists(clip["path"]):
                os.unlink(clip["path"])
            self.log_output.append(f"Deleted: {os.path.basename(clip['path'])}")
            self.results_table.removeRow(idx)
            self.results.pop(idx)
        except Exception as e:
            self.log_output.append(f"Delete failed: {e}")
