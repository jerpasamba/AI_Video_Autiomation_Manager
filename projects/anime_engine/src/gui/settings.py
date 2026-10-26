import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QSpinBox, QDoubleSpinBox,
    QCheckBox, QFormLayout, QGroupBox, QFileDialog,
    QMessageBox, QTabWidget
)
from PyQt6.QtCore import Qt


class SettingsTab(QWidget):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        tabs = QTabWidget()
        tabs.addTab(self._video_tab(), "Video")
        tabs.addTab(self._audio_tab(), "Audio")
        tabs.addTab(self._youtube_tab(), "YouTube")
        layout.addWidget(tabs)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("💾 Save Settings")
        save_btn.clicked.connect(self.save_settings)
        btn_layout.addStretch()
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

    def _video_tab(self):
        tab = QWidget()
        form = QFormLayout(tab)

        self.intro_text = QLineEdit(self.config["intro_text"])
        form.addRow("Intro Text:", self.intro_text)

        self.outro_text = QLineEdit(self.config["outro_text"])
        form.addRow("Outro Text:", self.outro_text)

        info = QLabel("Scenes are detected automatically at natural boundaries.\nNo min/max duration — each scene keeps its original length.")
        info.setStyleSheet("color: gray; padding: 4px;")
        form.addRow(info)

        self.top_n = QSpinBox()
        self.top_n.setRange(1, 20)
        self.top_n.setValue(self.config["scene_detection"]["top_n_clips"])
        form.addRow("Clips per Video:", self.top_n)

        return tab

    def _audio_tab(self):
        tab = QWidget()
        form = QFormLayout(tab)

        self.music_vol = QDoubleSpinBox()
        self.music_vol.setRange(0.0, 1.0)
        self.music_vol.setSingleStep(0.05)
        self.music_vol.setValue(self.config["background_music_volume"])
        form.addRow("Music Volume:", self.music_vol)

        return tab

    def _youtube_tab(self):
        tab = QWidget()
        form = QFormLayout(tab)

        self.client_secret_path = QLineEdit(
            self.config["youtube"]["client_secret_file"]
        )
        self.client_secret_path.setPlaceholderText("Path to client_secret.json")
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_secret)

        path_layout = QHBoxLayout()
        path_layout.addWidget(self.client_secret_path)
        path_layout.addWidget(browse_btn)
        form.addRow("Client Secret:", path_layout)

        self.upload_cb = QCheckBox()
        self.upload_cb.setChecked(self.config["youtube"]["upload_enabled"])
        form.addRow("Enable Upload:", self.upload_cb)

        self.default_tags = QLineEdit(
            ", ".join(self.config["youtube"]["default_tags"])
        )
        form.addRow("Default Tags (comma):", self.default_tags)

        guide_text = QLabel(
            "How to get a client_secret.json:\n"
            "1. Go to https://console.cloud.google.com\n"
            "2. Create a project → Enable YouTube Data API v3\n"
            "3. Credentials → Create OAuth 2.0 Client ID → Desktop app\n"
            "4. Click DOWNLOAD JSON → save the file somewhere safe\n"
            "5. Click Browse... above and select that downloaded .json file\n"
            "\n"
            "On first upload: a browser will open asking you to log into\n"
            "Google and authorize the app. Just click 'Continue'."
        )
        guide_text.setStyleSheet("color: gray; padding: 8px;")
        guide_text.setWordWrap(True)
        form.addRow(guide_text)

        return tab

    def _browse_secret(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select client_secret.json", "", "JSON Files (*.json)"
        )
        if path:
            self.client_secret_path.setText(path)

    def save_settings(self):
        self.config["intro_text"] = self.intro_text.text()
        self.config["outro_text"] = self.outro_text.text()
        self.config["scene_detection"]["top_n_clips"] = self.top_n.value()
        self.config["background_music_volume"] = self.music_vol.value()
        self.config["youtube"]["client_secret_file"] = self.client_secret_path.text()
        self.config["youtube"]["upload_enabled"] = self.upload_cb.isChecked()

        tags = [t.strip() for t in self.default_tags.text().split(",") if t.strip()]
        self.config["youtube"]["default_tags"] = tags

        self.config.save()
        QMessageBox.information(self, "Saved", "Settings saved successfully!")
