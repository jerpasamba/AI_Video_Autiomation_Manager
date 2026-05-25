import os
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QSpinBox, QCheckBox, QFrame,
    QProgressBar,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont

from app.queue_manager import TaskStatus
from ui.theme import COLORS, btn_style


class QueueTab(QWidget):
    def __init__(self, queue_manager, config, parent=None):
        super().__init__(parent)
        self.queue = queue_manager
        self.config = config
        self._last_task_count = 0

        layout = QVBoxLayout()
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        header_layout = QHBoxLayout()
        header = QLabel("Task Queue")
        header.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {COLORS['text_primary']};")
        header_layout.addWidget(header)

        header_layout.addStretch()

        self.auto_refill_check = QCheckBox("Auto-Refill")
        self.auto_refill_check.setChecked(config.get("auto_refill", True))
        self.auto_refill_check.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 13px;")
        header_layout.addWidget(self.auto_refill_check)

        self.auto_refill_check.stateChanged.connect(self._on_auto_refill_changed)

        self.pause_btn = QPushButton("Pause" if not self.queue.paused else "Resume")
        self.pause_btn.setStyleSheet(btn_style(COLORS['accent_yellow'], COLORS['accent_yellow_hover']))
        self.pause_btn.clicked.connect(self._toggle_pause)
        header_layout.addWidget(self.pause_btn)

        self.paused_label = QLabel("QUEUE PAUSED" if self.queue.paused else "")
        self.paused_label.setStyleSheet(f"color: {COLORS['accent_red']}; font-weight: bold; padding-left: 10px;")
        header_layout.addWidget(self.paused_label)

        clear_failed_btn = QPushButton("Clear Failed")
        clear_failed_btn.setStyleSheet(btn_style(COLORS['bg_input'], COLORS['border'], COLORS['text_secondary']))
        clear_failed_btn.clicked.connect(self.queue.clear_failed)
        header_layout.addWidget(clear_failed_btn)

        cancel_all_btn = QPushButton("Cancel All")
        cancel_all_btn.setStyleSheet(btn_style(COLORS['accent_red'], COLORS['accent_red_hover'], "white"))
        cancel_all_btn.clicked.connect(self._cancel_all)
        header_layout.addWidget(cancel_all_btn)

        layout.addLayout(header_layout)

        # Active queue table
        active_label = QLabel("Active Queue")
        active_label.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {COLORS['text_primary']}; margin-top: 8px;")
        layout.addWidget(active_label)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(["Task ID", "Type", "Title", "Status", "Progress", "Step", "Created", ""])
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(7, 80)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background: {COLORS['bg_card']}; color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']}; border-radius: 8px;
                gridline-color: {COLORS['border']};
            }}
            QTableWidget::item {{ padding: 8px; }}
            QHeaderView::section {{
                background: {COLORS['bg_medium']}; color: {COLORS['text_secondary']};
                border: none; border-bottom: 1px solid {COLORS['border']};
                padding: 10px; font-weight: bold;
            }}
        """)
        layout.addWidget(self.table)

        cancel_btn = QPushButton("Cancel Selected")
        cancel_btn.setStyleSheet(btn_style(COLORS['accent_red'], COLORS['accent_red_hover']))
        cancel_btn.clicked.connect(self._cancel_selected)
        layout.addWidget(cancel_btn)

        # Upload History section (permanent)
        history_label = QLabel("Upload History (permanent)")
        history_label.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {COLORS['text_primary']}; margin-top: 16px;")
        layout.addWidget(history_label)

        self.history_table = QTableWidget()
        self.history_table.setColumnCount(4)
        self.history_table.setHorizontalHeaderLabels(["Video", "Platform", "Status", "Date"])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.history_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.history_table.setStyleSheet(f"""
            QTableWidget {{
                background: {COLORS['bg_card']}; color: {COLORS['text_secondary']};
                border: 1px solid {COLORS['border']}; border-radius: 8px;
                gridline-color: {COLORS['border']}; font-size: 12px;
            }}
            QTableWidget::item {{ padding: 4px; }}
            QHeaderView::section {{
                background: {COLORS['bg_medium']}; color: {COLORS['text_dim']};
                border: none; border-bottom: 1px solid {COLORS['border']};
                padding: 6px; font-weight: bold; font-size: 11px;
            }}
        """)
        self.history_table.setMaximumHeight(150)
        layout.addWidget(self.history_table)

        self.setLayout(layout)

        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self.refresh_table)
        self._refresh_timer.start(2000)

    def refresh_table(self):
        tasks = self.queue.get_tasks()
        active = [t for t in tasks if t.status in (TaskStatus.PENDING, TaskStatus.RUNNING)]
        completed_uploads = [t for t in tasks if t.status == TaskStatus.COMPLETED and t.type.value == "upload_video"]

        self.table.setRowCount(len(active))

        status_colors = {
            TaskStatus.PENDING: QColor(COLORS["status_pending"]),
            TaskStatus.RUNNING: QColor(COLORS["status_running"]),
            TaskStatus.COMPLETED: QColor(COLORS["status_success"]),
            TaskStatus.FAILED: QColor(COLORS["status_fail"]),
            TaskStatus.CANCELLED: QColor(COLORS["text_dim"]),
        }

        type_labels = {
            "manhwa_chapter": "Manhwa",
            "anime_short": "Anime",
            "minecraft_story": "Minecraft",
            "upload_video": "Upload",
        }

        for row, task in enumerate(active):
            color = status_colors.get(task.status, QColor(COLORS["text_primary"]))

            id_item = QTableWidgetItem(task.id)
            id_item.setForeground(color)
            self.table.setItem(row, 0, id_item)

            type_item = QTableWidgetItem(type_labels.get(task.type.value, task.type.value))
            type_item.setForeground(color)
            self.table.setItem(row, 1, type_item)

            title_item = QTableWidgetItem(task.title[:50])
            title_item.setForeground(color)
            self.table.setItem(row, 2, title_item)

            status_item = QTableWidgetItem(task.status.value)
            status_item.setForeground(color)
            self.table.setItem(row, 3, status_item)

            if task.status == TaskStatus.RUNNING:
                progress_widget = QProgressBar()
                progress_widget.setValue(task.progress)
                progress_widget.setStyleSheet(f"""
                    QProgressBar {{
                        background: {COLORS['bg_input']}; border: none; border-radius: 4px;
                        height: 6px;
                    }}
                    QProgressBar::chunk {{ background: {COLORS['accent_blue']}; border-radius: 4px; }}
                """)
                progress_widget.setMinimumHeight(6)
                self.table.setCellWidget(row, 4, progress_widget)
                self.table.setItem(row, 4, QTableWidgetItem(""))
            else:
                progress_item = QTableWidgetItem(f"{task.progress}%")
                progress_item.setForeground(color)
                self.table.setItem(row, 4, progress_item)

            step_item = QTableWidgetItem(task.step_name[:30] if task.step_name else "-")
            step_item.setForeground(color)
            self.table.setItem(row, 5, step_item)

            created = task.created_at.split(".")[0] if task.created_at else "-"
            time_item = QTableWidgetItem(created)
            time_item.setForeground(color)
            self.table.setItem(row, 6, time_item)

            cancel_cell = QPushButton("Cancel")
            cancel_cell.setStyleSheet(btn_style(COLORS['accent_red'], COLORS['accent_red_hover'], "white", padding="4px 10px"))
            cancel_cell.clicked.connect(lambda checked, tid=task.id: self.queue.cancel_task(tid))
            self.table.setCellWidget(row, 7, cancel_cell)

        if active and len(active) > self._last_task_count:
            self.table.scrollToBottom()
        self._last_task_count = len(active)

        # Populate history table
        self.history_table.setRowCount(len(completed_uploads))
        for row, task in enumerate(completed_uploads):
            vp = task.params.get("video_path", "")
            video_name = os.path.basename(vp) if vp else "?"
            platform = task.params.get("platform", "?")
            date = task.completed_at.split(".")[0] if task.completed_at else "-"

            self.history_table.setItem(row, 0, QTableWidgetItem(video_name[:40]))
            self.history_table.setItem(row, 1, QTableWidgetItem(platform))
            status_item = QTableWidgetItem("Uploaded")
            status_item.setForeground(QColor(COLORS["status_success"]))
            self.history_table.setItem(row, 2, status_item)
            self.history_table.setItem(row, 3, QTableWidgetItem(date))

    def _toggle_pause(self):
        if self.queue.paused:
            self.queue.resume()
        else:
            self.queue.pause()
        self.pause_btn.setText("Pause" if not self.queue.paused else "Resume")
        self.paused_label.setText("QUEUE PAUSED" if self.queue.paused else "")

    def _cancel_selected(self):
        row = self.table.currentRow()
        if row >= 0:
            id_item = self.table.item(row, 0)
            if id_item:
                self.queue.cancel_task(id_item.text())

    def _cancel_all(self):
        for t in self.queue.get_tasks():
            if t.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
                self.queue.cancel_task(t.id)
        self.queue.clear_failed()

    def _on_auto_refill_changed(self, state):
        self.config["auto_refill"] = state == Qt.CheckState.Checked.value
