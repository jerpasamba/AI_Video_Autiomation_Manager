import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QFrame, QGroupBox,
    QFormLayout, QFileDialog, QMessageBox,
    QSpinBox, QTextEdit, QCheckBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ui.theme import COLORS, btn_style, input_style, card_style


def _group_style():
    return f"""
        QGroupBox {{
            background: {COLORS['bg_card']}; border: 1px solid {COLORS['border']};
            border-radius: 10px; margin-top: 12px; padding: 20px;
            font-weight: bold; color: {COLORS['text_primary']};
        }}
    """


class SettingsTab(QWidget):
    def __init__(self, config, main_window, parent=None):
        super().__init__(parent)
        self.config = config
        self.main_window = main_window

        layout = QVBoxLayout()
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        header = QLabel("Settings")
        header.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {COLORS['text_primary']};")
        layout.addWidget(header)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout()
        scroll_layout.setSpacing(16)

        # --- Facebook ---
        fb_group = QGroupBox("Facebook Reels Upload")
        fb_group.setStyleSheet(_group_style())
        fb_form = QFormLayout()
        fb_form.setSpacing(10)

        self.fb_page_id = QLineEdit()
        self.fb_page_id.setText(config.get("facebook", {}).get("page_id", "61589862161579"))
        self.fb_page_id.setStyleSheet(input_style())
        fb_form.addRow("Page ID:", self.fb_page_id)

        self.fb_access_token = QLineEdit()
        self.fb_access_token.setText(config.get("facebook", {}).get("access_token", ""))
        self.fb_access_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.fb_access_token.setStyleSheet(input_style())
        fb_form.addRow("Access Token:", self.fb_access_token)

        fb_instructions = QLabel(
            "To get your Facebook Page Access Token:\n"
            "1. Go to developers.facebook.com/tools/explorer/\n"
            "2. Select your App → Page → get Page Token\n"
            "3. Must have: pages_manage_posts, pages_read_engagement\n"
            "4. Click 'Test Connection' to verify\n"
            "NOTE: User Tokens won't work for Reels uploads - use a Page Token!\n"
            "Tip: You can also set env vars FACEBOOK_PAGE_ID and FACEBOOK_ACCESS_TOKEN (recommended)"
        )
        fb_instructions.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; padding: 8px;")
        fb_instructions.setWordWrap(True)
        fb_form.addRow("", fb_instructions)

        fb_test_btn = QPushButton("Test Facebook Connection")
        fb_test_btn.setStyleSheet(btn_style(COLORS['facebook'], COLORS['facebook_hover'], "white"))
        fb_test_btn.clicked.connect(self._test_facebook)
        fb_form.addRow("", fb_test_btn)

        fb_group.setLayout(fb_form)
        scroll_layout.addWidget(fb_group)

        # --- YouTube ---
        yt_group = QGroupBox("YouTube Upload")
        yt_group.setStyleSheet(_group_style())
        yt_form = QFormLayout()
        yt_form.setSpacing(10)

        self.yt_client_secret = QLineEdit()
        yt_cfg = config.get("youtube", {})
        existing = yt_cfg.get("client_secret_file", "")
        auto_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "client_secret.json")
        if not existing and os.path.exists(auto_path):
            existing = auto_path
            config.setdefault("youtube", {})["client_secret_file"] = auto_path
        self.yt_client_secret.setText(existing)
        self.yt_client_secret.setStyleSheet(input_style())
        yt_browse = QPushButton("Browse...")
        yt_browse.setStyleSheet(btn_style(COLORS['bg_input'], COLORS['border'], COLORS['text_secondary']))
        yt_browse.clicked.connect(self._browse_client_secret)

        yt_path_layout = QHBoxLayout()
        yt_path_layout.addWidget(self.yt_client_secret)
        yt_path_layout.addWidget(yt_browse)
        yt_form.addRow("Client Secret:", yt_path_layout)

        yt_auto_note = QLabel("Tip: Place client_secret.json in the project folder and it's auto-detected.")
        yt_auto_note.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; padding: 4px 8px;")
        yt_form.addRow("", yt_auto_note)

        yt_test_btn = QPushButton("Test YouTube Connection")
        yt_test_btn.setStyleSheet(btn_style(COLORS['accent_green'], COLORS['accent_green_hover']))
        yt_test_btn.clicked.connect(self._test_youtube)
        yt_form.addRow("", yt_test_btn)

        # Enable/disable auto-upload to YouTube
        self.yt_upload_enabled = QCheckBox("Enable YouTube Auto-Upload")
        self.yt_upload_enabled.setChecked(config.get("youtube", {}).get("upload_enabled", False))
        self.yt_upload_enabled.setStyleSheet(f"color: {COLORS['text_primary']};")
        yt_form.addRow("", self.yt_upload_enabled)

        # Optional automation
        self.yt_playlists_enabled = QCheckBox("Auto-add uploads to Manhwa playlist")
        self.yt_playlists_enabled.setChecked(config.get("youtube", {}).get("playlists_enabled", False))
        self.yt_playlists_enabled.setStyleSheet(f"color: {COLORS['text_primary']};")
        yt_form.addRow("", self.yt_playlists_enabled)

        self.yt_shorts_enabled = QCheckBox("Auto-generate 60s Short (Manhwa)")
        self.yt_shorts_enabled.setChecked(config.get("youtube", {}).get("shorts_enabled", False))
        self.yt_shorts_enabled.setStyleSheet(f"color: {COLORS['text_primary']};")
        yt_form.addRow("", self.yt_shorts_enabled)

        yt_group.setLayout(yt_form)
        scroll_layout.addWidget(yt_group)

        # --- Project Paths ---
        paths_group = QGroupBox("Project Paths")
        paths_group.setStyleSheet(_group_style())
        paths_form = QFormLayout()
        paths_form.setSpacing(10)

        self.manhwa_path = QLineEdit()
        self.manhwa_path.setText(config.get("manhwa_project_path", "projects/manhwa_engine"))
        self.manhwa_path.setStyleSheet(input_style())
        paths_form.addRow("Manhwa:", self.manhwa_path)

        self.anime_path = QLineEdit()
        self.anime_path.setText(config.get("anime_shorts_path", "projects/anime_engine"))
        self.anime_path.setStyleSheet(input_style())
        paths_form.addRow("Anime Shorts:", self.anime_path)

        self.minecraft_path = QLineEdit()
        self.minecraft_path.setText(config.get("minecraft_path", "projects/minecraft_engine"))
        self.minecraft_path.setStyleSheet(input_style())
        paths_form.addRow("Minecraft:", self.minecraft_path)

        paths_group.setLayout(paths_form)
        scroll_layout.addWidget(paths_group)

        # --- General ---
        general_group = QGroupBox("General Settings")
        general_group.setStyleSheet(_group_style())
        general_form = QFormLayout()
        general_form.setSpacing(10)

        self.worker_count = QSpinBox()
        self.worker_count.setMinimum(1)
        self.worker_count.setMaximum(4)
        self.worker_count.setValue(config.get("worker_count", 2))
        self.worker_count.setStyleSheet(f"""
            QSpinBox {{
                background: {COLORS['bg_input']}; color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']}; border-radius: 6px; padding: 8px;
            }}
        """)
        general_form.addRow("Worker Count:", self.worker_count)

        self.auto_refill_setting = QCheckBox("Auto-refill queue when empty")
        self.auto_refill_setting.setChecked(config.get("auto_refill", True))
        self.auto_refill_setting.setStyleSheet(f"color: {COLORS['text_primary']};")
        general_form.addRow("", self.auto_refill_setting)

        self.auto_upload_setting = QCheckBox("Auto-upload generated videos")
        self.auto_upload_setting.setChecked(config.get("auto_upload", False))
        self.auto_upload_setting.setStyleSheet(f"color: {COLORS['text_primary']};")
        general_form.addRow("", self.auto_upload_setting)

        general_group.setLayout(general_form)
        scroll_layout.addWidget(general_group)

        save_btn = QPushButton("Save Settings")
        save_btn.setStyleSheet(btn_style(COLORS['accent_blue'], COLORS['accent_blue_hover'], padding="12px 24px", radius=8))
        save_btn.clicked.connect(self._save_settings)
        scroll_layout.addWidget(save_btn)

        scroll_content.setLayout(scroll_layout)
        layout.addWidget(scroll_content)
        self.setLayout(layout)

    def _browse_client_secret(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select client_secret.json", "",
            "JSON Files (*.json);;All Files (*.*)"
        )
        if path:
            self.yt_client_secret.setText(path)

    def _test_youtube(self):
        from upload.youtube_uploader import verify_auth
        self.config.setdefault("youtube", {})["client_secret_file"] = self.yt_client_secret.text()
        ok, msg = verify_auth(self.config)
        if ok:
            QMessageBox.information(self, "YouTube Test", f"Authenticated")
        else:
            QMessageBox.warning(self, "YouTube Test", f"{msg}")

    def _test_facebook(self):
        from upload.facebook_uploader import verify_token
        self.config.setdefault("facebook", {})
        self.config["facebook"]["access_token"] = self.fb_access_token.text()
        self.config["facebook"]["page_id"] = self.fb_page_id.text()
        ok, msg = verify_token(self.config)
        if ok:
            QMessageBox.information(self, "Facebook Test", f"Authenticated: {msg}")
        else:
            QMessageBox.warning(self, "Facebook Test", f"{msg}")

    def _save_settings(self):
        self.config["manhwa_project_path"] = self.manhwa_path.text()
        self.config["anime_shorts_path"] = self.anime_path.text()
        self.config["minecraft_path"] = self.minecraft_path.text()
        self.config.setdefault("youtube", {})["client_secret_file"] = self.yt_client_secret.text()
        self.config["youtube"]["upload_enabled"] = self.yt_upload_enabled.isChecked()
        self.config["youtube"]["playlists_enabled"] = self.yt_playlists_enabled.isChecked()
        self.config["youtube"]["shorts_enabled"] = self.yt_shorts_enabled.isChecked()
        self.config.setdefault("facebook", {})
        self.config["facebook"]["page_id"] = self.fb_page_id.text()
        self.config["facebook"]["access_token"] = self.fb_access_token.text()
        self.config["worker_count"] = self.worker_count.value()
        self.config["auto_refill"] = self.auto_refill_setting.isChecked()
        self.config["auto_upload"] = self.auto_upload_setting.isChecked()
        self.main_window.save_config()
        QMessageBox.information(self, "Settings Saved", "Settings have been saved.")
