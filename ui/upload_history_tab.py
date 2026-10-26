import os
import logging
import webbrowser
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QGroupBox, QMessageBox, QFrame,
    QLineEdit, QComboBox, QProgressBar, QMenu,
    QDialog, QFormLayout, QApplication, QCheckBox, QSpinBox,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QAction, QCursor



from ui.theme import COLORS, btn_style, card_style, input_style
from app.video_verifier import (
    format_count, build_video_url, verify_entry, BatchVerifierWorker
)

log = logging.getLogger("video_manager_ui")

PLATFORM_COLORS = {
    "youtube": QColor(COLORS["youtube"]),
    "youtube_short": QColor(COLORS["youtube"]),
    "facebook": QColor(COLORS["facebook"]),
    "tiktok": QColor(COLORS["tiktok"]),
}

PLATFORM_LABELS = {
    "youtube": "YouTube",
    "youtube_short": "YouTube Shorts",
    "facebook": "Facebook Reel",
    "tiktok": "TikTok",
}


def _stat_card(title_or_widget, value_widget, accent_color, subtitle_widget=None, action_widget=None):
    """Helper to create executive KPI summary cards with optional header actions."""
    frame = QFrame()
    frame.setFrameShape(QFrame.Shape.StyledPanel)
    frame.setStyleSheet(f"""
        QFrame {{
            background: {COLORS['bg_card']};
            border: 1px solid {COLORS['border']};
            border-left: 4px solid {accent_color};
            border-radius: 8px;
            padding: 8px 14px;
        }}
    """)
    vbox = QVBoxLayout()
    vbox.setContentsMargins(4, 4, 4, 4)
    vbox.setSpacing(2)

    top_row = QHBoxLayout()
    top_row.setContentsMargins(0, 0, 0, 0)
    top_row.setSpacing(6)

    if isinstance(title_or_widget, QWidget):
        top_row.addWidget(title_or_widget)
    else:
        lbl_title = QLabel(str(title_or_widget))
        lbl_title.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; text-transform: uppercase; font-weight: bold;")
        top_row.addWidget(lbl_title)

    top_row.addStretch()
    if action_widget:
        top_row.addWidget(action_widget)

    vbox.addLayout(top_row)
    vbox.addWidget(value_widget)
    if subtitle_widget:
        vbox.addWidget(subtitle_widget)

    frame.setLayout(vbox)
    return frame


class UploadHistoryTab(QWidget):
    """Real-time Video Manager & Live Analytics Dashboard."""

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self._raw_items = []
        self._verifier_worker = None
        self._views_mode = "highest"  # "highest" or "total"
        self._highest_views = 0
        self._highest_title = ""
        self._total_views = 0

        layout = QVBoxLayout()
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        # 1. Header Section
        header_layout = QHBoxLayout()
        header_text_layout = QVBoxLayout()
        header = QLabel("Video Manager & Live Analytics")
        header.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {COLORS['text_primary']};")
        header_text_layout.addWidget(header)

        sub_header = QLabel("Live status checker, engagement metrics, and video health across all social platforms")
        sub_header.setStyleSheet(f"font-size: 12px; color: {COLORS['text_secondary']};")
        header_text_layout.addWidget(sub_header)
        header_layout.addLayout(header_text_layout)

        header_layout.addStretch()

        self.btn_sync_channel = QPushButton("⚡ Auto-Sync Channel")
        self.btn_sync_channel.setStyleSheet(btn_style(COLORS['accent_blue'], COLORS['accent_blue_hover'], "white", padding="9px 16px", radius=6))
        self.btn_sync_channel.clicked.connect(self._sync_channel_dialog)
        header_layout.addWidget(self.btn_sync_channel)

        self.btn_track_url = QPushButton("➕ Track Link (Manual)")
        self.btn_track_url.setStyleSheet(btn_style(COLORS['bg_input'], COLORS['border'], COLORS['text_secondary'], padding="9px 14px", radius=6))
        self.btn_track_url.clicked.connect(self._track_video_url_dialog)
        header_layout.addWidget(self.btn_track_url)

        self.btn_scan_local = QPushButton("📂 Scan Local Files")
        self.btn_scan_local.setStyleSheet(btn_style(COLORS['bg_input'], COLORS['border'], COLORS['text_primary'], padding="9px 14px", radius=6))
        self.btn_scan_local.clicked.connect(self._scan_local_videos_dialog)
        header_layout.addWidget(self.btn_scan_local)


        self.btn_refresh_views = QPushButton("🔄 Check & Refresh Live Views")
        self.btn_refresh_views.setStyleSheet(btn_style(COLORS['accent_green'], COLORS['accent_green_hover'], "white", padding="9px 18px", radius=6))
        self.btn_refresh_views.clicked.connect(self._start_batch_verification)
        header_layout.addWidget(self.btn_refresh_views)

        self.btn_reload = QPushButton("Reload")
        self.btn_reload.setStyleSheet(btn_style(COLORS['bg_input'], COLORS['border'], COLORS['text_secondary'], padding="9px 14px", radius=6))
        self.btn_reload.clicked.connect(self._load_history)
        header_layout.addWidget(self.btn_reload)

        clear_btn = QPushButton("Clear History")
        clear_btn.setStyleSheet(btn_style(COLORS['bg_input'], COLORS['accent_red'], COLORS['accent_red'], padding="9px 14px", radius=6))
        clear_btn.clicked.connect(self._clear_history)
        header_layout.addWidget(clear_btn)


        layout.addLayout(header_layout)

        # 2. KPI Summary Cards
        kpi_layout = QHBoxLayout()
        kpi_layout.setSpacing(12)

        self.val_total = QLabel("0")
        self.val_total.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {COLORS['text_primary']};")
        self.lbl_sub_total = QLabel("Catalog")
        self.lbl_sub_total.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
        kpi_layout.addWidget(_stat_card("Total Videos", self.val_total, COLORS['accent_blue'], self.lbl_sub_total))

        self.lbl_views_title = QLabel("Highest Views 🏆")
        self.lbl_views_title.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; text-transform: uppercase; font-weight: bold;")

        self.val_views = QLabel("--")
        self.val_views.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {COLORS['accent_green']};")

        self.lbl_top_video = QLabel("No views yet")
        self.lbl_top_video.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")

        self.btn_switch_views_mode = QPushButton("⇄ Total")
        self.btn_switch_views_mode.setToolTip("Switch between Highest Views 🏆 and Total Views 👁️")
        self.btn_switch_views_mode.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_switch_views_mode.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['bg_input']};
                color: {COLORS['accent_green']};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                padding: 1px 7px;
                font-size: 10px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {COLORS['accent_green']};
                color: white;
            }}
        """)
        self.btn_switch_views_mode.clicked.connect(self._toggle_views_mode)

        kpi_layout.addWidget(_stat_card(
            self.lbl_views_title, self.val_views, COLORS['accent_green'],
            subtitle_widget=self.lbl_top_video, action_widget=self.btn_switch_views_mode
        ))

        self.val_likes = QLabel("--")
        self.val_likes.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {COLORS['accent_pink']};")
        self.lbl_sub_likes = QLabel("Total engagement")
        self.lbl_sub_likes.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
        kpi_layout.addWidget(_stat_card("Total Likes ❤️", self.val_likes, COLORS['accent_pink'], self.lbl_sub_likes))

        self.val_comments = QLabel("--")
        self.val_comments.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {COLORS['accent_yellow']};")
        self.lbl_sub_comments = QLabel("Total comments")
        self.lbl_sub_comments.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
        kpi_layout.addWidget(_stat_card("Total Comments 💬", self.val_comments, COLORS['accent_yellow'], self.lbl_sub_comments))

        self.val_verified = QLabel("--")
        self.val_verified.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {COLORS['accent_teal']};")
        self.lbl_sub_verified = QLabel("Live status")
        self.lbl_sub_verified.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
        kpi_layout.addWidget(_stat_card("Verified Live ✅", self.val_verified, COLORS['accent_teal'], self.lbl_sub_verified))

        layout.addLayout(kpi_layout)

        # 3. Filter & Search Bar
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(10)

        filter_lbl = QLabel("Filter:")
        filter_lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-weight: bold;")
        filter_layout.addWidget(filter_lbl)

        self.platform_filter = QComboBox()
        self.platform_filter.addItems(["All Platforms", "YouTube", "YouTube Shorts", "Facebook Reels", "TikTok"])
        self.platform_filter.setStyleSheet(input_style(padding="6px 12px"))
        self.platform_filter.currentIndexChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.platform_filter)

        self.status_filter = QComboBox()
        self.status_filter.addItems(["All Statuses", "Verified Live", "Processing", "Needs Attention / Failed", "Unchecked"])
        self.status_filter.setStyleSheet(input_style(padding="6px 12px"))
        self.status_filter.currentIndexChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.status_filter)

        self.sort_filter = QComboBox()
        self.sort_filter.addItems(["Sort: Highest Views 🔥", "Sort: Newest Uploads 🕒", "Sort: Most Likes ❤️", "Sort: Most Comments 💬", "Sort: Title (A-Z)"])
        self.sort_filter.setStyleSheet(input_style(padding="6px 12px"))
        self.sort_filter.currentIndexChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.sort_filter)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search by video name or title...")
        self.search_box.setStyleSheet(input_style(padding="6px 12px"))
        self.search_box.textChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.search_box, 1)

        self.btn_check_selected = QPushButton("Check Selected")
        self.btn_check_selected.setStyleSheet(btn_style(COLORS['bg_input'], COLORS['border'], COLORS['text_primary'], padding="6px 12px", radius=6))
        self.btn_check_selected.clicked.connect(self._verify_selected_row)
        filter_layout.addWidget(self.btn_check_selected)

        self.btn_open_video = QPushButton("Open Link 🌐")
        self.btn_open_video.setStyleSheet(btn_style(COLORS['accent_blue'], COLORS['accent_blue_hover'], "white", padding="6px 12px", radius=6))
        self.btn_open_video.clicked.connect(self._open_selected_video)
        filter_layout.addWidget(self.btn_open_video)

        layout.addLayout(filter_layout)

        # Verification Progress Bar (hidden by default)
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background: {COLORS['bg_input']}; border: 1px solid {COLORS['border']};
                border-radius: 4px; text-align: center; color: {COLORS['text_primary']}; height: 18px; font-size: 11px;
            }}
            QProgressBar::chunk {{ background: {COLORS['accent_green']}; border-radius: 3px; }}
        """)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # 4. Main Video Manager Table
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Date", "Video / Title", "Platform", "Live Verification",
            "Views 👁️", "Likes ❤️", "Comments 💬", "Last Checked", "Live URL"
        ])
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background: {COLORS['bg_medium']}; color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']}; border-radius: 8px;
                gridline-color: {COLORS['border']};
                font-size: 12px;
            }}
            QTableWidget::item {{ padding: 7px 10px; }}
            QTableWidget::item:selected {{ background: {COLORS['border']}; }}
            QHeaderView::section {{
                background: {COLORS['bg_card']}; color: {COLORS['text_secondary']};
                padding: 9px; border: 1px solid {COLORS['border']};
                font-weight: bold; font-size: 11px;
            }}
        """)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.itemDoubleClicked.connect(self._on_table_double_clicked)

        layout.addWidget(self.table)
        self.setLayout(layout)

        # Background reload timer
        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self._load_history)
        self._refresh_timer.start(15000)

        self._load_history()

    def _load_history(self):
        """Load records from uploads.json and populate table with cached metrics."""
        from app import upload_registry
        try:
            reg = upload_registry.load_registry()
            self._raw_items = reg.get("items", []) or []
        except Exception as e:
            log.warning("Failed loading upload history: %s", e)
            self._raw_items = []

        self._apply_filter()

    def _apply_filter(self):
        """Filter and sort table records based on search query, dropdown filters, and sorting criteria."""
        search_query = self.search_box.text().strip().lower()
        platform_sel = self.platform_filter.currentText()
        status_sel = self.status_filter.currentText()
        sort_mode = self.sort_filter.currentText() if hasattr(self, 'sort_filter') else "Sort: Highest Views 🔥"

        self.table.setRowCount(0)

        total_videos = 0
        total_views = 0
        highest_views = 0
        highest_title = ""
        total_likes = 0
        total_comments = 0
        verified_live_count = 0

        matched_items = []

        for entry in self._raw_items:
            platform = entry.get("platform", "unknown")
            vpath = entry.get("path", "")
            fname = os.path.basename(vpath) if vpath else "Video"
            metrics = entry.get("metrics") or {}
            live_status = metrics.get("status") or ("Uploaded" if entry.get("remote_id") else "Unverified")

            # Check Platform Filter
            if platform_sel == "YouTube" and platform != "youtube":
                continue
            if platform_sel == "YouTube Shorts" and platform != "youtube_short":
                continue
            if platform_sel == "Facebook Reels" and platform != "facebook":
                continue
            if platform_sel == "TikTok" and platform != "tiktok":
                continue

            # Check Status Filter
            if status_sel == "Verified Live" and "Verified" not in live_status:
                continue
            if status_sel == "Processing" and live_status != "Processing":
                continue
            if status_sel == "Needs Attention / Failed" and ("Not Found" not in live_status and "Deleted" not in live_status and "Failed" not in live_status and "Error" not in live_status):
                continue
            if status_sel == "Unchecked" and metrics:
                continue

            # Check Search Query
            title_text = metrics.get("title") or fname
            if search_query and search_query not in fname.lower() and search_query not in title_text.lower():
                continue

            total_videos += 1
            views_num = metrics.get("views") or 0
            likes_num = metrics.get("likes") or 0
            comm_num = metrics.get("comments") or 0

            total_views += views_num
            if views_num > highest_views:
                highest_views = views_num
                highest_title = title_text

            total_likes += likes_num
            total_comments += comm_num
            if metrics.get("verified") or "Verified" in live_status:
                verified_live_count += 1

            matched_items.append((entry, metrics))

        # Sort filtered items
        if "Highest Views" in sort_mode:
            matched_items.sort(key=lambda x: (x[1].get("views") or 0), reverse=True)
        elif "Most Likes" in sort_mode:
            matched_items.sort(key=lambda x: (x[1].get("likes") or 0), reverse=True)
        elif "Most Comments" in sort_mode:
            matched_items.sort(key=lambda x: (x[1].get("comments") or 0), reverse=True)
        elif "Title" in sort_mode:
            matched_items.sort(key=lambda x: (x[1].get("title") or os.path.basename(x[0].get("path", ""))).lower())
        else:  # Newest Uploads
            matched_items.sort(key=lambda x: x[0].get("uploaded_at") or "", reverse=True)

        for entry, metrics in matched_items:
            self._insert_table_row(entry, metrics)

        # Update KPI Summary Cards
        self.val_total.setText(str(len(matched_items)))
        if hasattr(self, 'lbl_sub_total'):
            self.lbl_sub_total.setText(f"{len(self._raw_items)} total catalog")

        self._highest_views = highest_views
        self._highest_title = highest_title
        self._total_views = total_views
        self._refresh_views_card()

        self.val_likes.setText(format_count(total_likes) if total_likes > 0 else "--")
        if hasattr(self, 'lbl_sub_likes'):
            self.lbl_sub_likes.setText(f"{total_likes:,} total" if total_likes > 0 else "0 total")

        self.val_comments.setText(format_count(total_comments) if total_comments > 0 else "--")
        if hasattr(self, 'lbl_sub_comments'):
            self.lbl_sub_comments.setText(f"{total_comments:,} total" if total_comments > 0 else "0 total")

        self.val_verified.setText(f"{verified_live_count} / {len(matched_items)}")
        if hasattr(self, 'lbl_sub_verified'):
            self.lbl_sub_verified.setText("Active links")

    def _toggle_views_mode(self):
        """Toggle KPI Views display between Highest Views and Total Views."""
        self._views_mode = "total" if self._views_mode == "highest" else "highest"
        self._refresh_views_card()

    def _refresh_views_card(self):
        """Update the Views KPI card based on the current mode (highest vs total)."""
        if not hasattr(self, 'lbl_views_title') or not hasattr(self, 'val_views'):
            return

        if self._views_mode == "highest":
            self.lbl_views_title.setText("Highest Views 🏆")
            self.btn_switch_views_mode.setText("⇄ Total")
            self.btn_switch_views_mode.setToolTip("Currently showing highest single video views. Click to switch to Total Views 👁️")
            if self._highest_views > 0:
                self.val_views.setText(format_count(self._highest_views))
                clean_top = self._highest_title.replace("_video.mp4", "").replace("_shorts.mp4", "").replace(".mp4", "")
                if len(clean_top) > 20:
                    clean_top = clean_top[:18] + "…"
                if hasattr(self, 'lbl_top_video'):
                    self.lbl_top_video.setText(f"Top: {clean_top}")
                tooltip_msg = (
                    f"🏆 Highest Performing Video:\n"
                    f"{self._highest_title}\n\n"
                    f"👁️ Peak Views: {self._highest_views:,}\n"
                    f"📊 Combined Views (Filtered): {self._total_views:,}\n\n"
                    f"💡 Click '⇄ Total' to switch to combined total views"
                )
                self.val_views.setToolTip(tooltip_msg)
                if hasattr(self, 'lbl_top_video'):
                    self.lbl_top_video.setToolTip(tooltip_msg)
            else:
                self.val_views.setText("--")
                if hasattr(self, 'lbl_top_video'):
                    self.lbl_top_video.setText("No views recorded")
                self.val_views.setToolTip("No live views recorded yet")
                if hasattr(self, 'lbl_top_video'):
                    self.lbl_top_video.setToolTip("")
        else:
            self.lbl_views_title.setText("Total Views 👁️")
            self.btn_switch_views_mode.setText("⇄ Highest")
            self.btn_switch_views_mode.setToolTip("Currently showing total cumulative views. Click to switch to Highest Views 🏆")
            if self._total_views > 0:
                self.val_views.setText(format_count(self._total_views))
                if hasattr(self, 'lbl_top_video'):
                    self.lbl_top_video.setText(f"{self._total_views:,} combined")
                tooltip_msg = (
                    f"📊 Total Combined Views: {self._total_views:,}\n\n"
                    f"🏆 Peak Video: {self._highest_title} ({self._highest_views:,} views)\n\n"
                    f"💡 Click '⇄ Highest' to switch to highest video views"
                )
                self.val_views.setToolTip(tooltip_msg)
                if hasattr(self, 'lbl_top_video'):
                    self.lbl_top_video.setToolTip(tooltip_msg)
            else:
                self.val_views.setText("--")
                if hasattr(self, 'lbl_top_video'):
                    self.lbl_top_video.setText("0 total views")
                self.val_views.setToolTip("No live views recorded yet")
                if hasattr(self, 'lbl_top_video'):
                    self.lbl_top_video.setToolTip("")

    def _insert_table_row(self, entry, metrics):
        row = self.table.rowCount()
        self.table.insertRow(row)

        vpath = entry.get("path", "")
        fname = os.path.basename(vpath) if vpath else "Video"
        platform = entry.get("platform", "unknown")
        remote_id = entry.get("remote_id", "")
        url = build_video_url(platform, remote_id, entry.get("url"))

        # Date
        ts = entry.get("uploaded_at", "")
        date_str = ts
        if ts:
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                date_str = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                date_str = ts[:16]

        # Title
        display_title = metrics.get("title") or fname.replace("_video.mp4", "").replace("_shorts.mp4", "").replace(".mp4", "").replace("_", " ").title()

        # Live status
        if metrics:
            st = metrics.get("status", "Verified Live")
            if "Verified" in st:
                status_icon = "🟢"
                status_color = QColor(COLORS["status_success"])
            elif "Processing" in st:
                status_icon = "🟡"
                status_color = QColor(COLORS["status_running"])
            elif "Not Found" in st or "Deleted" in st:
                status_icon = "🔴"
                status_color = QColor(COLORS["status_fail"])
            else:
                status_icon = "⚪"
                status_color = QColor(COLORS["text_secondary"])
            status_text = f"{status_icon} {st}"
        else:
            status_text = "⚪ Uploaded (Unchecked)"
            status_color = QColor(COLORS["text_muted"])

        views_str = metrics.get("views_str") or "--"
        likes_str = metrics.get("likes_str") or "--"
        comments_str = metrics.get("comments_str") or "--"

        checked_at = metrics.get("checked_at", "")
        if checked_at:
            try:
                dt_c = datetime.fromisoformat(checked_at)
                checked_str = dt_c.strftime("%H:%M:%S")
            except Exception:
                checked_str = checked_at[-8:]
        else:
            checked_str = "Never"

        # Set Columns
        item_date = self._set_item(row, 0, date_str)
        item_date.setData(Qt.ItemDataRole.UserRole, entry)

        item_title = self._set_item(row, 1, display_title)
        item_title.setToolTip(f"File: {vpath}\nRemote ID: {remote_id}")

        plat_item = self._set_item(row, 2, PLATFORM_LABELS.get(platform, platform.title()))
        if platform in PLATFORM_COLORS:
            plat_item.setForeground(PLATFORM_COLORS[platform])
            f = plat_item.font()
            f.setBold(True)
            plat_item.setFont(f)

        item_status = self._set_item(row, 3, status_text)
        item_status.setForeground(status_color)

        item_views = self._set_item(row, 4, f"👁️ {views_str}")
        if views_str != "--":
            item_views.setForeground(QColor(COLORS["accent_green"]))

        item_likes = self._set_item(row, 5, f"❤️ {likes_str}")
        if likes_str != "--":
            item_likes.setForeground(QColor(COLORS["accent_pink"]))

        item_comms = self._set_item(row, 6, f"💬 {comments_str}")

        item_checked = self._set_item(row, 7, checked_str)
        item_checked.setForeground(QColor(COLORS["text_muted"]))

        item_url = self._set_item(row, 8, url or "--")
        if url:
            item_url.setForeground(QColor(COLORS["accent_blue"]))
            font = QFont()
            font.setUnderline(True)
            item_url.setFont(font)
            item_url.setToolTip(f"Click to open: {url}")

    def _set_item(self, row, col, text):
        item = QTableWidgetItem(str(text))
        self.table.setItem(row, col, item)
        return item

    def _start_batch_verification(self):
        """Launch background checker to verify all videos and update live metrics."""
        if not self._raw_items:
            QMessageBox.information(self, "No Videos", "No uploaded videos found in history to verify.")
            return

        if self._verifier_worker and self._verifier_worker.isRunning():
            QMessageBox.information(self, "Checking in Progress", "Verification is already running in the background.")
            return

        self.btn_refresh_views.setEnabled(False)
        self.btn_refresh_views.setText("⏳ Checking Live Metrics...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(self._raw_items))
        self.progress_bar.setValue(0)

        self._verifier_worker = BatchVerifierWorker(self._raw_items, self.config, self)
        self._verifier_worker.progress.connect(self._on_verifier_progress)
        self._verifier_worker.item_verified.connect(self._on_item_verified)
        self._verifier_worker.finished.connect(self._on_verifier_finished)
        self._verifier_worker.start()

    def _on_verifier_progress(self, current, total, text):
        self.progress_bar.setValue(current)
        self.progress_bar.setFormat(f"{text} ({current}/{total})")

    def _on_item_verified(self, entry, metrics):
        # Update raw item in-memory
        for it in self._raw_items:
            if it.get("path") == entry.get("path") and it.get("platform") == entry.get("platform"):
                it["metrics"] = metrics
                break
        self._apply_filter()

    def _on_verifier_finished(self, summary):
        self.btn_refresh_views.setEnabled(True)
        self.btn_refresh_views.setText("🔄 Check & Refresh Live Views")
        self.progress_bar.setVisible(False)
        self._apply_filter()

        QMessageBox.information(
            self,
            "Verification Complete",
            f"Verified {summary.get('verified_count')}/{summary.get('total_checked')} videos successfully!\n\n"
            f"• Total Live Views: {summary.get('total_views_str')}\n"
            f"• Total Likes: {summary.get('total_likes_str')}\n"
            f"• Total Comments: {summary.get('total_comments_str')}",
        )

    def _verify_selected_row(self):
        """Verify the currently selected video."""
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.information(self, "Select Video", "Please select a video row in the table first.")
            return

        row = selected_rows[0].row()
        entry_item = self.table.item(row, 0)
        entry = entry_item.data(Qt.ItemDataRole.UserRole)
        if not entry:
            return

        self.btn_check_selected.setEnabled(False)
        self.btn_check_selected.setText("Checking...")
        try:
            metrics = verify_entry(entry, self.config)
            from app import upload_registry
            upload_registry.update_item_metrics(entry.get("path"), entry.get("platform"), metrics)
            for it in self._raw_items:
                if it.get("path") == entry.get("path") and it.get("platform") == entry.get("platform"):
                    it["metrics"] = metrics
                    break
            self._apply_filter()
            QMessageBox.information(
                self,
                "Video Verified",
                f"Status: {metrics.get('status')}\n"
                f"Views: {metrics.get('views_str')}\n"
                f"Likes: {metrics.get('likes_str')}\n"
                f"Comments: {metrics.get('comments_str')}\n"
                f"URL: {metrics.get('url')}",
            )
        finally:
            self.btn_check_selected.setEnabled(True)
            self.btn_check_selected.setText("Check Selected")

    def _open_selected_video(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.information(self, "Select Video", "Please select a video row first.")
            return
        row = selected_rows[0].row()
        url_item = self.table.item(row, 8)
        if url_item and url_item.text().startswith("http"):
            webbrowser.open(url_item.text())
        else:
            QMessageBox.warning(self, "No URL", "No web link available for this video.")

    def _on_table_double_clicked(self, item):
        row = item.row()
        url_item = self.table.item(row, 8)
        if url_item and url_item.text().startswith("http"):
            webbrowser.open(url_item.text())

    def _show_context_menu(self, pos):
        item = self.table.itemAt(pos)
        if not item:
            return
        row = item.row()
        entry_item = self.table.item(row, 0)
        entry = entry_item.data(Qt.ItemDataRole.UserRole) if entry_item else None
        url_item = self.table.item(row, 8)
        url = url_item.text() if url_item and url_item.text().startswith("http") else None

        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background: {COLORS['bg_card']}; color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']}; border-radius: 6px; padding: 4px;
            }}
            QMenu::item:selected {{ background: {COLORS['accent_blue']}; color: white; }}
        """)

        act_verify = QAction("🔍 Check Status & Views", self)
        act_verify.triggered.connect(self._verify_selected_row)
        menu.addAction(act_verify)

        if url:
            act_open = QAction("🌐 Open Live Video in Browser", self)
            act_open.triggered.connect(lambda: webbrowser.open(url))
            menu.addAction(act_open)

            act_copy = QAction("📋 Copy Video URL", self)
            from PyQt6.QtWidgets import QApplication
            act_copy.triggered.connect(lambda: QApplication.clipboard().setText(url))
            menu.addAction(act_copy)

        if entry and entry.get("path"):
            vpath = entry["path"]
            act_path = QAction("📁 Copy Local File Path", self)
            from PyQt6.QtWidgets import QApplication
            act_path.triggered.connect(lambda: QApplication.clipboard().setText(vpath))
            menu.addAction(act_path)

        menu.addSeparator()
        act_delete = QAction("🗑️ Remove from History", self)
        act_delete.triggered.connect(lambda: self._delete_entry(entry, row))
        menu.addAction(act_delete)

        menu.exec(QCursor.pos())

    def _delete_entry(self, entry, row):
        if not entry:
            return
        from app import upload_registry
        reg = upload_registry.load_registry()
        reg_items = reg.get("items", [])
        new_items = [
            it for it in reg_items
            if not (it.get("path") == entry.get("path") and it.get("platform") == entry.get("platform"))
        ]
        reg["items"] = new_items
        upload_registry.save_registry(reg)
        self._load_history()


    def _clear_history(self):
        reply = QMessageBox.question(
            self, "Clear History",
            "Remove all upload history entries?\n(Videos already on social media will NOT be deleted.)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        from app import upload_registry
        reg = upload_registry.load_registry()
        reg["items"] = []
        upload_registry.save_registry(reg)
        self._load_history()

    def _sync_channel_dialog(self):
        """Automatically sync all published videos from YouTube channel or Facebook page."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Auto-Sync Channel Videos")
        dlg.setMinimumWidth(520)
        dlg.setStyleSheet(f"background: {COLORS['bg_dark']}; color: {COLORS['text_primary']};")

        layout = QVBoxLayout()
        layout.setSpacing(14)
        layout.setContentsMargins(18, 18, 18, 18)

        intro_box = QFrame()
        intro_box.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['bg_card']}; border: 1px solid {COLORS['border']};
                border-left: 4px solid {COLORS['accent_blue']}; border-radius: 6px; padding: 10px;
            }}
        """)
        intro_l = QVBoxLayout(intro_box)
        intro_t1 = QLabel("⚡ Automatic Channel Import")
        intro_t1.setStyleSheet(f"font-weight: bold; font-size: 13px; color: {COLORS['text_primary']};")
        intro_t2 = QLabel("Scan and automatically import all videos from your YouTube Channel or Facebook Page without pasting links one-by-one.")
        intro_t2.setWordWrap(True)
        intro_t2.setStyleSheet(f"font-size: 11px; color: {COLORS['text_secondary']};")
        intro_l.addWidget(intro_t1)
        intro_l.addWidget(intro_t2)
        layout.addWidget(intro_box)

        form = QFormLayout()
        form.setVerticalSpacing(12)

        plat_combo = QComboBox()
        plat_combo.addItems(["YouTube Channel", "Facebook Page Reels", "TikTok Account"])
        plat_combo.setStyleSheet(input_style())
        form.addRow("Platform:", plat_combo)

        default_handle = self.config.get("youtube_channel_handle", "")
        if not default_handle:
            try:
                import json
                anime_cfg_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "projects", "anime_engine", "src", "config.json"
                )
                if os.path.exists(anime_cfg_path):
                    with open(anime_cfg_path, encoding="utf-8") as f:
                        default_handle = json.load(f).get("channel_handle", "@ZeroBalanceManhwa")
            except Exception:
                default_handle = "@ZeroBalanceManhwa"

        handle_lbl = QLabel("Channel Handle / URL:")
        handle_input = QLineEdit()
        handle_input.setText(default_handle or "@ZeroBalanceManhwa")
        handle_input.setPlaceholderText("e.g. @ZeroBalanceManhwa or https://youtube.com/@channel")
        handle_input.setStyleSheet(input_style())
        form.addRow(handle_lbl, handle_input)

        def on_plat_changed(idx):
            if idx == 0:
                handle_lbl.setText("Channel Handle / URL:")
                handle_input.setText(self.config.get("youtube_channel_handle", "@ZeroBalanceManhwa"))
                handle_input.setPlaceholderText("e.g. @ZeroBalanceManhwa or https://youtube.com/@channel")
            elif idx == 1:
                handle_lbl.setText("Facebook Page ID / URL:")
                handle_input.setText(self.config.get("facebook", {}).get("page_id", "61595561175384"))
                handle_input.setPlaceholderText("e.g. 61595561175384 or https://facebook.com/page")
            else:
                handle_lbl.setText("TikTok Handle / Profile URL:")
                handle_input.setText(self.config.get("tiktok_channel_handle", "@ZeroBalanceManhwa"))
                handle_input.setPlaceholderText("e.g. @ZeroBalanceManhwa or https://tiktok.com/@ZeroBalanceManhwa")

        plat_combo.currentIndexChanged.connect(on_plat_changed)


        max_spin = QSpinBox()
        max_spin.setRange(5, 200)
        max_spin.setValue(30)
        max_spin.setStyleSheet(f"""
            QSpinBox {{
                background: {COLORS['bg_input']}; color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']}; border-radius: 6px; padding: 6px;
            }}
        """)
        form.addRow("Max Videos to Fetch:", max_spin)

        auto_sync_chk = QCheckBox("Automatically sync this channel on app startup (Optional)")
        auto_sync_chk.setChecked(self.config.get("auto_sync_channel_enabled", True))
        auto_sync_chk.setStyleSheet(f"color: {COLORS['text_primary']};")
        form.addRow("", auto_sync_chk)

        layout.addLayout(form)

        btn_box = QHBoxLayout()
        btn_box.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setStyleSheet(btn_style(COLORS['bg_input'], COLORS['border'], COLORS['text_primary'], padding="8px 16px", radius=6))
        btn_cancel.clicked.connect(dlg.reject)
        btn_box.addWidget(btn_cancel)

        btn_sync = QPushButton("⚡ Scan & Auto-Import All")
        btn_sync.setStyleSheet(btn_style(COLORS['accent_blue'], COLORS['accent_blue_hover'], "white", padding="8px 20px", radius=6))

        def do_sync():
            identifier = handle_input.text().strip()
            if not identifier:
                QMessageBox.warning(dlg, "Error", "Please enter a valid channel handle or URL.")
                return

            plat_text = plat_combo.currentText()
            if "YouTube" in plat_text:
                platform = "youtube"
            elif "Facebook" in plat_text:
                platform = "facebook"
            else:
                platform = "tiktok"

            btn_sync.setEnabled(False)
            btn_sync.setText(f"⏳ Scanning {plat_text}...")
            QApplication.processEvents()

            if platform == "youtube":
                self.config["youtube_channel_handle"] = identifier
            elif platform == "facebook":
                if "facebook" not in self.config:
                    self.config["facebook"] = {}
                self.config["facebook"]["page_id"] = identifier
            elif platform == "tiktok":
                self.config["tiktok_channel_handle"] = identifier
            self.config["auto_sync_channel_enabled"] = auto_sync_chk.isChecked()
            from app import upload_registry

            try:
                from app.video_verifier import sync_channel_videos
                videos = sync_channel_videos(identifier, platform=platform, max_results=max_spin.value(), config=self.config)
                if not videos:
                    if platform == "facebook":
                        msg = (
                            f"No published reels found on Facebook Page '{identifier}' yet.\n\n"
                            "Since this is a brand new Page with 0 videos, once you publish your first Reel, "
                            "it will be detected and tracked here!"
                        )
                    elif platform == "tiktok":
                        msg = (
                            f"No public videos found on TikTok account '{identifier}' yet.\n\n"
                            "Tip: If your TikTok account is private or new, you can also track individual videos using the 'Track URL 🔗' button!"
                        )
                    else:
                        msg = f"Could not retrieve videos for '{identifier}'. Please check the channel handle or internet connection."
                    QMessageBox.information(dlg, "No Videos Found", msg)
                    btn_sync.setEnabled(True)
                    btn_sync.setText("⚡ Scan & Auto-Import All")
                    return


                existing_ids = {str(it.get("remote_id")).strip() for it in self._raw_items if it.get("remote_id")}
                added_count = 0

                for v in videos:
                    rid = str(v["remote_id"]).strip()
                    if rid not in existing_ids:
                        v_metrics = {
                            "verified": True,
                            "status": "Verified Live",
                            "views": v.get("views") or 0,
                            "views_str": str(v.get("views")) if v.get("views") else "--",
                            "likes": 0,
                            "likes_str": "--",
                            "comments": 0,
                            "comments_str": "--",
                            "title": v.get("title", ""),
                            "url": v["url"],
                            "checked_at": datetime.now().isoformat(),
                            "error": None,
                        }
                        upload_registry.record_upload(
                            video_path=v["url"],
                            platform=platform,
                            remote_id=rid,
                            url=v["url"],
                            metrics=v_metrics,
                        )
                        existing_ids.add(rid)
                        added_count += 1

                self._load_history()
                dlg.accept()

                QMessageBox.information(
                    self,
                    "Channel Sync Complete",
                    f"⚡ Auto-Sync Complete!\n\n"
                    f"Channel: {identifier}\n"
                    f"Videos Found on Channel: {len(videos)}\n"
                    f"New Videos Added: {added_count}\n"
                    f"Already in Manager: {len(videos) - added_count}\n\n"
                    f"Your channel videos are now fully tracked in Video Manager!",
                )
            except Exception as ex:
                log.error("Channel sync failed: %s", ex)
                QMessageBox.critical(dlg, "Sync Failed", f"Error during sync: {ex}")
            finally:
                btn_sync.setEnabled(True)
                btn_sync.setText("⚡ Scan & Auto-Import All")

        btn_sync.clicked.connect(do_sync)
        btn_box.addWidget(btn_sync)

        layout.addLayout(btn_box)
        dlg.setLayout(layout)
        dlg.exec()

    def _track_video_url_dialog(self):
        """Allow user to track any external or pre-existing video by URL (manual/optional)."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Track Video URL (Manual / Optional)")
        dlg.setMinimumWidth(500)
        dlg.setStyleSheet(f"background: {COLORS['bg_dark']}; color: {COLORS['text_primary']};")

        form = QFormLayout()
        form.setVerticalSpacing(14)
        form.setHorizontalSpacing(16)

        tip_box = QFrame()
        tip_box.setStyleSheet(f"background: {COLORS['bg_card']}; border: 1px solid {COLORS['border']}; border-radius: 6px; padding: 8px;")
        tip_layout = QHBoxLayout(tip_box)
        tip_lbl = QLabel("💡 Tip: Want all channel videos automatically?")
        tip_lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
        tip_btn = QPushButton("Open Auto-Sync ⚡")
        tip_btn.setStyleSheet(btn_style(COLORS['accent_blue'], COLORS['accent_blue_hover'], "white", padding="4px 10px", radius=4))
        tip_btn.clicked.connect(lambda: (dlg.reject(), self._sync_channel_dialog()))
        tip_layout.addWidget(tip_lbl)
        tip_layout.addWidget(tip_btn)
        form.addRow("", tip_box)

        plat_combo = QComboBox()
        plat_combo.addItems(["YouTube", "TikTok", "Facebook Reels"])
        plat_combo.setStyleSheet(input_style())
        form.addRow("Platform:", plat_combo)


        url_input = QLineEdit()
        url_input.setPlaceholderText("e.g. https://www.youtube.com/watch?v=... or TikTok link")
        url_input.setStyleSheet(input_style())
        form.addRow("Video URL:", url_input)

        title_input = QLineEdit()
        title_input.setPlaceholderText("Optional display title")
        title_input.setStyleSheet(input_style())
        form.addRow("Custom Title:", title_input)

        btn_box = QHBoxLayout()
        btn_box.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setStyleSheet(btn_style(COLORS['bg_input'], COLORS['border'], COLORS['text_primary'], padding="8px 16px", radius=6))
        btn_cancel.clicked.connect(dlg.reject)
        btn_box.addWidget(btn_cancel)

        btn_add = QPushButton("Verify & Start Tracking")
        btn_add.setStyleSheet(btn_style(COLORS['accent_green'], COLORS['accent_green_hover'], "white", padding="8px 18px", radius=6))

        def on_add():
            url = url_input.text().strip()
            if not url or not url.startswith("http"):
                QMessageBox.warning(dlg, "Invalid URL", "Please enter a valid web link starting with http:// or https://")
                return

            plat_map = {
                "YouTube": "youtube",
                "TikTok": "tiktok",
                "Facebook Reels": "facebook",
            }
            platform = plat_map.get(plat_combo.currentText(), "youtube")

            btn_add.setEnabled(False)
            btn_add.setText("Checking live status...")
            QApplication.processEvents()

            from app.video_verifier import verify_entry
            from app import upload_registry

            remote_id = url.split("?v=")[-1].split("&")[0].split("/")[-1]
            entry = {
                "platform": platform,
                "url": url,
                "path": url,
                "remote_id": remote_id,
            }

            metrics = verify_entry(entry, self.config)
            display_title = title_input.text().strip() or metrics.get("title") or remote_id

            upload_registry.record_upload(
                video_path=url,
                platform=platform,
                remote_id=remote_id,
                url=url,
                metrics=metrics,
            )

            self._load_history()
            dlg.accept()

            status = metrics.get("status", "Unknown")
            views = metrics.get("views_str", "--")
            QMessageBox.information(
                self,
                "Video Added",
                f"Successfully added to Video Manager!\n\n"
                f"Title: {display_title}\n"
                f"Status: {status}\n"
                f"Live Views: {views}",
            )

        btn_add.clicked.connect(on_add)
        btn_box.addWidget(btn_add)
        form.addRow("", btn_box)

        dlg.setLayout(form)
        dlg.exec()

    def _scan_local_videos_dialog(self):
        """Scan local engine folders for generated videos and show their upload status."""
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        scan_targets = [
            ("Manhwa Engine", os.path.join(root, "projects", "manhwa_engine", "output")),
            ("Anime Shorts", os.path.join(root, "projects", "anime_engine", "output")),
            ("Movie Reels", os.path.join(root, "projects", "moviereels_engine", "output")),
            ("Minecraft Stories", os.path.join(root, "projects", "minecraft_engine", "output")),
        ]

        uploaded_paths = set()
        for it in self._raw_items:
            p = it.get("path")
            if p:
                uploaded_paths.add(os.path.normcase(os.path.abspath(p)))

        found_videos = []
        for engine_name, folder in scan_targets:
            if not os.path.exists(folder):
                continue
            for r, _, files in os.walk(folder):
                for f in files:
                    if f.lower().endswith(".mp4") and not f.startswith("_") and not f.endswith("_raw.mp4"):
                        fp = os.path.join(r, f)
                        try:
                            size_mb = os.path.getsize(fp) / (1024 * 1024)
                        except OSError:
                            size_mb = 0
                        norm_p = os.path.normcase(os.path.abspath(fp))
                        is_uploaded = norm_p in uploaded_paths
                        found_videos.append({
                            "engine": engine_name,
                            "name": f,
                            "path": fp,
                            "size_mb": size_mb,
                            "uploaded": is_uploaded,
                        })

        dlg = QDialog(self)
        dlg.setWindowTitle("Local Generated Videos Finder")
        dlg.setMinimumSize(780, 480)
        dlg.setStyleSheet(f"background: {COLORS['bg_dark']}; color: {COLORS['text_primary']};")

        dlg_layout = QVBoxLayout()
        dlg_layout.setSpacing(12)
        dlg_layout.setContentsMargins(16, 16, 16, 16)

        info_lbl = QLabel(f"Found {len(found_videos)} video file(s) across engine directories:")
        info_lbl.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {COLORS['text_primary']};")
        dlg_layout.addWidget(info_lbl)

        tbl = QTableWidget()
        tbl.setColumnCount(4)
        tbl.setHorizontalHeaderLabels(["Engine", "File Name", "Size (MB)", "Upload Status"])
        tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        tbl.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tbl.setStyleSheet(f"""
            QTableWidget {{
                background: {COLORS['bg_medium']}; color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']}; border-radius: 6px;
            }}
            QHeaderView::section {{
                background: {COLORS['bg_card']}; color: {COLORS['text_secondary']};
                padding: 6px; border: 1px solid {COLORS['border']}; font-weight: bold;
            }}
        """)

        tbl.setRowCount(len(found_videos))
        for r_idx, vid in enumerate(found_videos):
            item_eng = QTableWidgetItem(vid["engine"])
            tbl.setItem(r_idx, 0, item_eng)

            item_name = QTableWidgetItem(vid["name"])
            item_name.setToolTip(vid["path"])
            tbl.setItem(r_idx, 1, item_name)

            item_size = QTableWidgetItem(f"{vid['size_mb']:.1f} MB")
            tbl.setItem(r_idx, 2, item_size)

            if vid["uploaded"]:
                item_st = QTableWidgetItem("Uploaded / Tracked")
                item_st.setForeground(QColor(COLORS["accent_green"]))
            else:
                item_st = QTableWidgetItem("Ready to Upload")
                item_st.setForeground(QColor(COLORS["accent_yellow"]))
            tbl.setItem(r_idx, 3, item_st)

        dlg_layout.addWidget(tbl)

        btn_row = QHBoxLayout()
        btn_open_folder = QPushButton("📁 Open Selected Folder")
        btn_open_folder.setStyleSheet(btn_style(COLORS['bg_input'], COLORS['border'], COLORS['text_primary'], padding="8px 14px", radius=6))

        def open_folder():
            sel = tbl.selectionModel().selectedRows()
            if not sel:
                return
            idx = sel[0].row()
            vpath = found_videos[idx]["path"]
            if os.path.exists(vpath):
                import subprocess
                subprocess.run(f'explorer /select,"{vpath}"', shell=True)

        btn_open_folder.clicked.connect(open_folder)
        btn_row.addWidget(btn_open_folder)

        btn_row.addStretch()

        btn_close = QPushButton("Close")
        btn_close.setStyleSheet(btn_style(COLORS['accent_blue'], COLORS['accent_blue_hover'], "white", padding="8px 18px", radius=6))
        btn_close.clicked.connect(dlg.accept)
        btn_row.addWidget(btn_close)

        dlg_layout.addLayout(btn_row)
        dlg.setLayout(dlg_layout)
        dlg.exec()

