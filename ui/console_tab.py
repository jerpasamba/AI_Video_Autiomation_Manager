import logging
import io
import sys

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QCheckBox, QLabel, QFrame, QTabWidget,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QTextCursor, QColor, QFont

from ui.theme import COLORS


COLOR_MAP = {
    "manhwa": COLORS["accent_blue"],
    "anime": COLORS["accent_pink"],
    "minecraft": COLORS["accent_yellow"],
}


class QtLogHandler(logging.Handler, QObject):
    log_signal = pyqtSignal(str, str)

    LEVEL_COLORS = {
        "DEBUG": COLORS["log_debug"],
        "INFO": COLORS["log_info"],
        "SUCCESS": COLORS["log_success"],
        "WARNING": COLORS["log_warning"],
        "ERROR": COLORS["log_error"],
        "CRITICAL": COLORS["log_error"],
    }

    def __init__(self, logger_name=None):
        logging.Handler.__init__(self)
        QObject.__init__(self)
        self.logger_name = logger_name
        self.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))

    def emit(self, record):
        if self.logger_name and record.name != self.logger_name:
            return
        try:
            msg = self.format(record)
            level = record.levelname
            if level == "INFO" and "complete" in msg.lower():
                level = "SUCCESS"
            elif level == "INFO" and ("error" in msg.lower() or "fail" in msg.lower()):
                level = "ERROR"
            self.log_signal.emit(msg, level)
        except Exception:
            self.handleError(record)


class StdoutRedirector(QObject):
    write_signal = pyqtSignal(str)

    def __init__(self, original_stream):
        super().__init__()
        self._original = original_stream

    def write(self, text):
        if text.strip():
            self.write_signal.emit(text)
        self._original.write(text)

    def flush(self):
        self._original.flush()


class ConsoleWidget(QWidget):
    MAX_LINES = 5000

    def __init__(self, pipeline_name="", parent=None):
        super().__init__(parent)
        self._auto_scroll = True
        self._paused = False
        self.pipeline_name = pipeline_name

        layout = QVBoxLayout()
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)

        toolbar = QHBoxLayout()
        title_color = COLOR_MAP.get(pipeline_name, COLORS["text_primary"])
        title = QLabel(pipeline_name.title() if pipeline_name else "Console")
        title.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {title_color};")
        toolbar.addWidget(title)
        toolbar.addStretch()

        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setStyleSheet(self._tool_btn_style())
        self.pause_btn.clicked.connect(self._toggle_pause)
        toolbar.addWidget(self.pause_btn)

        self.auto_scroll_cb = QCheckBox("Auto-scroll")
        self.auto_scroll_cb.setChecked(True)
        self.auto_scroll_cb.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
        self.auto_scroll_cb.stateChanged.connect(
            lambda s: setattr(self, '_auto_scroll', s == Qt.CheckState.Checked.value)
        )
        toolbar.addWidget(self.auto_scroll_cb)

        clear_btn = QPushButton("Clear")
        clear_btn.setStyleSheet(self._tool_btn_style())
        clear_btn.clicked.connect(self._clear_log)
        toolbar.addWidget(clear_btn)

        layout.addLayout(toolbar)

        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setFont(QFont("Consolas", 10))
        self.log_display.setStyleSheet(f"""
            QTextEdit {{
                background: {COLORS['bg_dark']};
                color: {COLORS['text_secondary']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 8px;
                selection-background-color: {COLORS['border']};
            }}
        """)
        self.log_display.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.log_display.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self.log_display)

        self.setLayout(layout)

        self._handler = QtLogHandler(logger_name=pipeline_name if pipeline_name else None)
        self._handler.log_signal.connect(self._append_log)
        target_logger = logging.getLogger(pipeline_name) if pipeline_name else logging.getLogger()
        target_logger.addHandler(self._handler)
        target_logger.setLevel(logging.INFO)

        self._line_count = 0

    def _tool_btn_style(self):
        return f"""
            QPushButton {{
                background: {COLORS['bg_input']}; color: {COLORS['text_secondary']};
                border: 1px solid {COLORS['border']}; border-radius: 4px;
                padding: 3px 10px; font-size: 11px;
            }}
            QPushButton:hover {{ background: {COLORS['border']}; }}
        """

    def _toggle_pause(self):
        self._paused = not self._paused
        self.pause_btn.setText("Resume" if self._paused else "Pause")

    def _append_log(self, msg, level):
        if self._paused:
            return
        color = QtLogHandler.LEVEL_COLORS.get(level, COLORS["text_secondary"])
        prefix = {
            "DEBUG": "   ",
            "INFO": "   ",
            "SUCCESS": "   ",
            "WARNING": "   ",
            "ERROR": "   ",
            "CRITICAL": "   ",
        }.get(level, "   ")
        self._append_colored(f"{prefix}{msg}", color)

    def _append_colored(self, text, color):
        self._line_count += 1
        if self._line_count > self.MAX_LINES:
            cursor = self.log_display.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            cursor.movePosition(QTextCursor.MoveOperation.Down, QTextCursor.MoveMode.KeepAnchor, 1000)
            cursor.removeSelectedText()
            self._line_count -= 1000

        cursor = self.log_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = cursor.charFormat()
        fmt.setForeground(QColor(color))
        cursor.setCharFormat(fmt)
        cursor.insertText(text + "\n")
        if self._auto_scroll:
            self.log_display.setTextCursor(cursor)
            self.log_display.ensureCursorVisible()

    def _clear_log(self):
        self.log_display.clear()
        self._line_count = 0

    def close_handler(self):
        target_logger = logging.getLogger(self.pipeline_name) if self.pipeline_name else logging.getLogger()
        target_logger.removeHandler(self._handler)
        self._handler.close()


class ConsoleTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        tabs = QTabWidget()
        tabs.setDocumentMode(True)

        self.manhwa_console = ConsoleWidget("manhwa")
        self.anime_console = ConsoleWidget("anime")
        self.minecraft_console = ConsoleWidget("minecraft")

        tabs.addTab(self.manhwa_console, "Manhwa")
        tabs.addTab(self.anime_console, "Anime")
        tabs.addTab(self.minecraft_console, "Minecraft")

        layout.addWidget(tabs)
        self.setLayout(layout)

    def close_handler(self):
        self.manhwa_console.close_handler()
        self.anime_console.close_handler()
        self.minecraft_console.close_handler()
