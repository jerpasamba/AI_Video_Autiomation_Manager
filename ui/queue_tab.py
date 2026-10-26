import os
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QSpinBox, QCheckBox, QFrame,
    QProgressBar, QMessageBox
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
        layout.setSpacing(14)
        layout.setContentsMargins(24, 20, 24, 20)

        # Header bar
        header_layout = QHBoxLayout()
        header = QLabel("Task Queue & Processing")
        header.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {COLORS['text_primary']};")
        header_layout.addWidget(header)

        header_layout.addStretch()

        self.auto_refill_check = QCheckBox("Auto-Refill")
        self.auto_refill_check.setChecked(config.get("auto_refill", False))
        self.auto_refill_check.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 13px;")
        header_layout.addWidget(self.auto_refill_check)
        self.auto_refill_check.stateChanged.connect(self._on_auto_refill_changed)

        self.pause_btn = QPushButton("Pause" if not self.queue.paused else "Resume")
        self.pause_btn.setStyleSheet(btn_style(COLORS['accent_yellow'], COLORS['accent_yellow_hover']))
        self.pause_btn.clicked.connect(self._toggle_pause)
        header_layout.addWidget(self.pause_btn)

        self.paused_label = QLabel("QUEUE PAUSED" if self.queue.paused else "")
        self.paused_label.setStyleSheet(f"color: {COLORS['accent_red']}; font-weight: bold; padding-left: 6px;")
        header_layout.addWidget(self.paused_label)

        clear_failed_btn = QPushButton("Clear Failed")
        clear_failed_btn.setStyleSheet(btn_style(COLORS['bg_input'], COLORS['border'], COLORS['text_secondary']))
        clear_failed_btn.clicked.connect(self.queue.clear_failed)
        header_layout.addWidget(clear_failed_btn)

        cancel_all_btn = QPushButton("Cancel All")
        cancel_all_btn.setStyleSheet(btn_style(COLORS['accent_yellow'], COLORS['accent_yellow_hover'], "#1a1a2e"))
        cancel_all_btn.clicked.connect(self._cancel_all)
        header_layout.addWidget(cancel_all_btn)

        clear_all_btn = QPushButton("🗑️ Clear Entire Queue")
        clear_all_btn.setStyleSheet(btn_style(COLORS['accent_red'], COLORS['accent_red_hover'], "white"))
        clear_all_btn.clicked.connect(self._clear_entire_queue)
        header_layout.addWidget(clear_all_btn)

        layout.addLayout(header_layout)

        # Live Worker Status Hero Banner
        self.status_banner = QFrame()
        self.status_banner.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1a2236, stop:1 #161b2b);
                border: 1px solid #334155;
                border-radius: 10px;
                padding: 12px;
            }}
        """)
        banner_layout = QVBoxLayout(self.status_banner)
        banner_layout.setContentsMargins(14, 12, 14, 12)
        banner_layout.setSpacing(8)

        self.banner_header_layout = QHBoxLayout()
        self.banner_title = QLabel("🟢 System Idle — No tasks currently running")
        self.banner_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #4ade80;")
        self.banner_header_layout.addWidget(self.banner_title)

        self.banner_header_layout.addStretch()

        self.banner_stats = QLabel("Pending: 0  |  Running: 0  |  Total: 0")
        self.banner_stats.setStyleSheet(f"font-size: 12px; color: {COLORS['text_dim']}; font-weight: bold;")
        self.banner_header_layout.addWidget(self.banner_stats)

        banner_layout.addLayout(self.banner_header_layout)

        # Container for running tasks list inside banner
        self.running_tasks_container = QWidget()
        self.running_tasks_layout = QVBoxLayout(self.running_tasks_container)
        self.running_tasks_layout.setContentsMargins(0, 0, 0, 0)
        self.running_tasks_layout.setSpacing(6)
        banner_layout.addWidget(self.running_tasks_container)

        layout.addWidget(self.status_banner)

        # Active queue table header
        active_header_layout = QHBoxLayout()
        active_label = QLabel("Active Queue (Running tasks at top)")
        active_label.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {COLORS['text_primary']};")
        active_header_layout.addWidget(active_label)
        active_header_layout.addStretch()

        layout.addLayout(active_header_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(["Task ID", "Type", "Title", "Status", "Progress", "Active Step", "Created", "Action"])
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(7, 85)
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

        table_btn_layout = QHBoxLayout()
        cancel_btn = QPushButton("Cancel Selected")
        cancel_btn.setStyleSheet(btn_style(COLORS['accent_red'], COLORS['accent_red_hover']))
        cancel_btn.clicked.connect(self._cancel_selected)
        table_btn_layout.addWidget(cancel_btn)
        table_btn_layout.addStretch()
        layout.addLayout(table_btn_layout)

        # Upload History section (permanent)
        history_label = QLabel("Recent Upload History")
        history_label.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {COLORS['text_primary']}; margin-top: 10px;")
        layout.addWidget(history_label)

        self.history_table = QTableWidget()
        self.history_table.setColumnCount(4)
        self.history_table.setHorizontalHeaderLabels(["Video File", "Platform", "Status", "Date"])
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
        self.history_table.setMaximumHeight(140)
        layout.addWidget(self.history_table)

        self.setLayout(layout)

        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self.refresh_table)
        self._refresh_timer.start(2000)

    def refresh_table(self):
        tasks = self.queue.get_tasks()
        active = [t for t in tasks if t.status in (TaskStatus.PENDING, TaskStatus.RUNNING)]
        running = [t for t in active if t.status == TaskStatus.RUNNING]
        pending = [t for t in active if t.status == TaskStatus.PENDING]
        completed_uploads = [t for t in tasks if t.status == TaskStatus.COMPLETED and t.type.value == "upload_video"]

        # Sort active tasks so running tasks are always at top
        active_sorted = running + pending

        # 1. Update Live Banner
        self._update_banner(running, len(pending), len(tasks))

        # 2. Update Active Table
        self.table.setRowCount(len(active_sorted))

        status_colors = {
            TaskStatus.PENDING: QColor(COLORS["status_pending"]),
            TaskStatus.RUNNING: QColor(COLORS["status_running"]),
            TaskStatus.COMPLETED: QColor(COLORS["status_success"]),
            TaskStatus.FAILED: QColor(COLORS["status_fail"]),
            TaskStatus.CANCELLED: QColor(COLORS["text_dim"]),
        }

        type_labels = {
            "manhwa_chapter": "📖 Manhwa",
            "anime_short": "🎬 Anime Short",
            "minecraft_story": "⛏️ Minecraft",
            "movie_reel": "🍿 Movie Clip",
            "upload_video": "🚀 Upload",
        }

        for row, task in enumerate(active_sorted):
            is_running = (task.status == TaskStatus.RUNNING)
            color = status_colors.get(task.status, QColor(COLORS["text_primary"]))

            id_item = QTableWidgetItem(task.id)
            id_item.setForeground(color)
            self.table.setItem(row, 0, id_item)

            type_item = QTableWidgetItem(type_labels.get(task.type.value, task.type.value))
            type_item.setForeground(color)
            self.table.setItem(row, 1, type_item)

            title_prefix = "⚡ " if is_running else ""
            title_item = QTableWidgetItem(f"{title_prefix}{task.title[:50]}")
            title_item.setForeground(color)
            self.table.setItem(row, 2, title_item)

            status_str = "⚡ RUNNING" if is_running else "🕒 PENDING"
            status_item = QTableWidgetItem(status_str)
            status_item.setForeground(color)
            if is_running:
                status_font = QFont()
                status_font.setBold(True)
                status_item.setFont(status_font)
            self.table.setItem(row, 3, status_item)

            if is_running:
                progress_widget = QProgressBar()
                progress_widget.setValue(task.progress)
                progress_widget.setStyleSheet(f"""
                    QProgressBar {{
                        background: {COLORS['bg_input']}; border: none; border-radius: 4px;
                        height: 8px; text-align: center;
                    }}
                    QProgressBar::chunk {{
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #38bdf8);
                        border-radius: 4px;
                    }}
                """)
                progress_widget.setMinimumHeight(8)
                self.table.setCellWidget(row, 4, progress_widget)
                self.table.setItem(row, 4, QTableWidgetItem(""))
            else:
                progress_item = QTableWidgetItem(f"{task.progress}%")
                progress_item.setForeground(color)
                self.table.setItem(row, 4, progress_item)

            step_text = task.step_name if task.step_name else ("Working..." if is_running else "Queued")
            step_item = QTableWidgetItem(step_text[:35])
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

        # 3. Populate history table
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

    def _update_banner(self, running_tasks, pending_count, total_count):
        self.banner_stats.setText(f"Pending: {pending_count}  |  Running: {len(running_tasks)}  |  Total: {total_count}")

        # Clear existing dynamic widgets in banner
        while self.running_tasks_layout.count():
            item = self.running_tasks_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if running_tasks:
            self.banner_title.setText(f"⚡ CURRENTLY WORKING ({len(running_tasks)} active task{'s' if len(running_tasks)>1 else ''}):")
            self.banner_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #38bdf8;")

            for t in running_tasks:
                card = QFrame()
                card.setStyleSheet("""
                    QFrame {
                        background: rgba(15, 23, 42, 0.7);
                        border: 1px solid #475569;
                        border-radius: 6px;
                        padding: 6px 10px;
                    }
                """)
                card_layout = QHBoxLayout(card)
                card_layout.setContentsMargins(8, 4, 8, 4)

                icon_label = QLabel("▶")
                icon_label.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 13px;")
                card_layout.addWidget(icon_label)

                title_lbl = QLabel(f"{t.title}  [{t.id}]")
                title_lbl.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 13px;")
                card_layout.addWidget(title_lbl)

                step_lbl = QLabel(f"• Step: {t.step_name or 'Processing...'}")
                step_lbl.setStyleSheet("color: #94a3b8; font-size: 12px;")
                card_layout.addWidget(step_lbl)

                card_layout.addStretch()

                pct_lbl = QLabel(f"{t.progress}%")
                pct_lbl.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 12px;")
                card_layout.addWidget(pct_lbl)

                pbar = QProgressBar()
                pbar.setValue(t.progress)
                pbar.setFixedWidth(120)
                pbar.setFixedHeight(8)
                pbar.setStyleSheet(f"""
                    QProgressBar {{
                        background: {COLORS['bg_input']}; border: none; border-radius: 4px;
                    }}
                    QProgressBar::chunk {{
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #38bdf8);
                        border-radius: 4px;
                    }}
                """)
                card_layout.addWidget(pbar)

                self.running_tasks_layout.addWidget(card)
        else:
            self.banner_title.setText("🟢 System Idle — No background tasks running")
            self.banner_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #4ade80;")

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
        self.refresh_table()

    def _clear_entire_queue(self):
        self.queue.clear_all()
        self.refresh_table()

    def _on_auto_refill_changed(self, state):
        self.config["auto_refill"] = state == Qt.CheckState.Checked.value
