import sys
import os

from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QApplication, QMessageBox, QStatusBar
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from src.config import Config
from src.pipeline import Pipeline
from src.gui.dashboard import DashboardTab
from src.gui.preview import PreviewTab
from src.gui.settings import SettingsTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Anime Shorts Generator")
        self.setMinimumSize(1000, 700)

        self.config = Config()
        self.pipeline = Pipeline(self.config)

        self.tabs = QTabWidget()
        self.dashboard = DashboardTab(self.pipeline)
        self.preview = PreviewTab(pipeline=self.pipeline)
        self.settings = SettingsTab(self.config)

        self.tabs.addTab(self.dashboard, "🎬 Dashboard")
        self.tabs.addTab(self.preview, "👁 Preview")
        self.tabs.addTab(self.settings, "⚙ Settings")

        self.setCentralWidget(self.tabs)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

        self.tabs.currentChanged.connect(self.on_tab_changed)

    def on_tab_changed(self, index):
        if self.tabs.tabText(index) == "👁 Preview":
            self.preview.refresh_list()

    def closeEvent(self, event):
        self.config.save()
        event.accept()
