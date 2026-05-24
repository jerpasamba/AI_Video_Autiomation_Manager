import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QListWidget, QLabel, QFileDialog, QFrame,
    QMessageBox, QCheckBox, QApplication,
)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget


class PreviewTab(QWidget):
    def __init__(self, pipeline=None):
        super().__init__()
        self.pipeline = pipeline
        self.current_video = None
        self.clip_paths = []
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        stats = QHBoxLayout()
        self.count_label = QLabel("0 shorts available")
        self.count_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFD700;")
        stats.addWidget(self.count_label)
        stats.addStretch()
        layout.addLayout(stats)

        content = QHBoxLayout()

        # Left: list panel
        list_panel = QVBoxLayout()
        list_panel.addWidget(QLabel("Generated Clips:"))

        self.clip_list = QListWidget()
        self.clip_list.setMinimumWidth(300)
        self.clip_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.clip_list.itemClicked.connect(self.load_clip)
        list_panel.addWidget(self.clip_list)

        list_controls = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_list)
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self.select_all)
        self.open_folder_btn = QPushButton("Open Folder")
        self.open_folder_btn.clicked.connect(self.open_output_folder)
        list_controls.addWidget(self.refresh_btn)
        list_controls.addWidget(self.select_all_btn)
        list_controls.addWidget(self.open_folder_btn)
        list_panel.addLayout(list_controls)

        # Upload section
        upload_group = QFrame()
        upload_group.setStyleSheet("QFrame { background: #1a1a2e; border-radius: 8px; padding: 10px; }")
        upload_layout = QVBoxLayout(upload_group)

        upload_layout.addWidget(QLabel("Upload to YouTube Shorts (Ctrl+click to select multiple):"))
        self.upload_btn = QPushButton(" Upload Selected to YouTube")
        self.upload_btn.setMinimumHeight(40)
        self.upload_btn.setStyleSheet("""
            QPushButton {
                font-size: 16px; font-weight: bold;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #ff4444, stop:1 #cc0000);
                color: white; border-radius: 8px;
            }
            QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #ff6666, stop:1 #ee2222); }
            QPushButton:disabled { background: #444; color: #888; }
        """)
        self.upload_btn.clicked.connect(self.upload_selected)
        upload_layout.addWidget(self.upload_btn)

        self.delete_after_cb = QCheckBox("Delete files after upload")
        self.delete_after_cb.setChecked(True)
        self.delete_after_cb.setStyleSheet("color: #aaa; font-size: 12px;")
        upload_layout.addWidget(self.delete_after_cb)

        self.upload_status = QLabel("")
        self.upload_status.setStyleSheet("color: #aaa; font-size: 12px;")
        upload_layout.addWidget(self.upload_status)

        list_panel.addWidget(upload_group)
        content.addLayout(list_panel, 1)

        # Right: video player
        player_panel = QVBoxLayout()
        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumSize(400, 500)
        self.video_widget.setStyleSheet("background: black;")
        player_panel.addWidget(self.video_widget)

        self.player = QMediaPlayer()
        self.player.setVideoOutput(self.video_widget)

        play_controls = QHBoxLayout()
        self.play_btn = QPushButton(" Play")
        self.play_btn.clicked.connect(self.toggle_play)
        play_controls.addStretch()
        play_controls.addWidget(self.play_btn)
        play_controls.addStretch()
        player_panel.addLayout(play_controls)

        # Info panel below player
        self.info_label = QLabel("Select a clip to preview")
        self.info_label.setStyleSheet("color: #888; font-size: 12px; padding: 4px;")
        self.info_label.setWordWrap(True)
        player_panel.addWidget(self.info_label)

        content.addLayout(player_panel, 2)
        layout.addLayout(content)

    def refresh_list(self):
        self.clip_list.clear()
        self.clip_paths = []
        shorts_dir = os.path.join("output", "shorts")
        count = 0
        if os.path.exists(shorts_dir):
            for f in sorted(os.listdir(shorts_dir)):
                if f.endswith("_shorts.mp4"):
                    full_path = os.path.join(shorts_dir, f)
                    self.clip_list.addItem(f)
                    self.clip_paths.append(full_path)
                    count += 1
        self.count_label.setText(f"{count} shorts available")

    def load_clip(self, item):
        idx = self.clip_list.row(item)
        if idx < 0 or idx >= len(self.clip_paths):
            return
        path = self.clip_paths[idx]
        if os.path.exists(path):
            self.current_video = path
            self.player.setSource(QUrl.fromLocalFile(path))
            self.player.play()
            self.play_btn.setText(" Pause")
            size_mb = os.path.getsize(path) / (1024 * 1024)
            self.info_label.setText(f"{os.path.basename(path)}  |  {size_mb:.1f} MB")

    def select_all(self):
        self.clip_list.selectAll()

    def toggle_play(self):
        if not self.current_video:
            return
        if self.player.playbackState() == self.player.PlaybackState.PlayingState:
            self.player.pause()
            self.play_btn.setText(" Play")
        else:
            self.player.play()
            self.play_btn.setText(" Pause")

    def upload_selected(self):
        if not self.pipeline:
            QMessageBox.warning(self, "Error", "No pipeline configured")
            return

        has_secret = bool(self.pipeline.config["youtube"].get("client_secret_file"))
        if not has_secret:
            QMessageBox.warning(self, "Upload Setup Required",
                                "Set your YouTube API client_secret.json in Settings tab first.")
            return

        items = self.clip_list.selectedItems()
        if not items:
            self.upload_status.setText("Select clips from the list first (Ctrl+click)")
            return

        total = len(items)
        success = 0
        self.upload_btn.setEnabled(False)
        self.upload_status.setText(f"Uploading 0/{total}...")

        for i, item in enumerate(items):
            idx = self.clip_list.row(item)
            if idx < 0 or idx >= len(self.clip_paths):
                continue
            path = self.clip_paths[idx]
            if not os.path.exists(path):
                continue

            name = os.path.basename(path)
            self.upload_status.setText(f"Uploading {i+1}/{total}: {name}...")
            QApplication.processEvents()

            try:
                self.pipeline.upload_clip(
                    {"path": path, "title": name.replace("_shorts.mp4", " #shorts"),
                     "description": f"Anime highlight\n\n{self.pipeline.config.get('channel_handle', '@animeshorts')}\n\n#anime #shorts #highlight"},
                    progress_callback=lambda msg: None
                )
                if self.delete_after_cb.isChecked():
                    if os.path.exists(path):
                        os.unlink(path)
                success += 1
            except Exception as e:
                err = str(e)
                if "access_denied" in err or "403" in err:
                    self.upload_status.setText(
                        "Google OAuth error — add your email as a test user in "
                        "Google Cloud Console > APIs & Services > OAuth consent screen"
                    )
                    QMessageBox.critical(self, "YouTube Upload Error",
                        "Google OAuth consent screen not verified.\n\n"
                        "1. Go to https://console.cloud.google.com/apis/credentials/consent\n"
                        "2. Add your Google email as a Test User\n"
                        "3. Wait 5 min, then try uploading again\n\n"
                        f"Error: {err[:100]}")
                else:
                    self.upload_status.setText(f"Failed: {name} - {err[:60]}")
                break

        self.upload_btn.setEnabled(True)
        self.upload_status.setText(f"Uploaded {success}/{total} shorts")
        self.refresh_list()

    def open_output_folder(self):
        path = os.path.join(os.getcwd(), "output", "shorts")
        if os.path.exists(path):
            os.startfile(path)
