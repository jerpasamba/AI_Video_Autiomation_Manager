import os
import json
import logging

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QListWidget, QListWidgetItem,
    QFrame, QCheckBox, QGroupBox, QSplitter,
    QMessageBox, QFileDialog, QMenu, QApplication,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QMimeData, QUrl
from PyQt6.QtGui import QColor, QDrag

from app.queue_manager import TaskType
from ui.theme import COLORS, btn_style, card_style

log = logging.getLogger("upload")

PLATFORM_STYLES = {
    "facebook": {
        "accent": COLORS["facebook"],
        "accent_hover": COLORS["facebook_hover"],
        "label": "Facebook Reels",
        "short_label": "FB",
    },
    "youtube": {
        "accent": COLORS["youtube"],
        "accent_hover": COLORS["youtube_hover"],
        "label": "YouTube (Full)",
        "short_label": "YT",
    },
    "youtube_short": {
        "accent": COLORS["youtube"],
        "accent_hover": COLORS["youtube_hover"],
        "label": "YouTube Shorts",
        "short_label": "YT#",
    },
    "tiktok": {
        "accent": COLORS["tiktok"],
        "accent_hover": COLORS["tiktok_hover"],
        "label": "TikTok",
        "short_label": "TT",
    },
}

SUPPORTED_VIDEO_EXTS = ('.mp4', '.mov', '.mkv', '.avi', '.webm')


class VideoDropZone(QFrame):
    """Interactive drag-and-drop area with platform selectors, browse button, and upload action."""
    files_selected = pyqtSignal(list, list)  # (paths, platforms)
    upload_all_requested = pyqtSignal()
    cleared = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._selected_files = []

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._apply_style(False)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 12, 14, 12)
        main_layout.setSpacing(10)

        # Top row: Drag prompt + Action buttons
        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        self.icon_label = QLabel("📥")
        self.icon_label.setStyleSheet("font-size: 26px;")
        top_row.addWidget(self.icon_label)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        self.title_label = QLabel("Drag & Drop Video Files Here")
        self.title_label.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {COLORS['text_primary']};")
        self.sub_label = QLabel("Drop files to stage them in 'Want to Upload' for the selected platforms below.")
        self.sub_label.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.sub_label)
        top_row.addLayout(text_layout)

        top_row.addStretch()

        self.browse_btn = QPushButton("📂 Browse Video Files...")
        self.browse_btn.setStyleSheet(btn_style(COLORS['accent_blue'], COLORS['accent_blue_hover'], "white", padding="7px 14px", radius=6))
        self.browse_btn.clicked.connect(self._on_browse)
        top_row.addWidget(self.browse_btn)

        self.upload_staged_btn = QPushButton("🚀 Upload All Staged Files")
        self.upload_staged_btn.setStyleSheet(btn_style(COLORS['accent_green'], COLORS['accent_green_hover'], "white", padding="7px 16px", radius=6))
        self.upload_staged_btn.setToolTip("Starts upload for all videos staged in 'Want to Upload' across all platforms")
        self.upload_staged_btn.clicked.connect(lambda: self.upload_all_requested.emit())
        top_row.addWidget(self.upload_staged_btn)

        main_layout.addLayout(top_row)

        # Bottom row: Target platform checkboxes & status
        plat_row = QHBoxLayout()
        plat_row.setSpacing(14)

        plat_lbl = QLabel("Stage Into:")
        plat_lbl.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {COLORS['text_secondary']};")
        plat_row.addWidget(plat_lbl)

        self.plat_checkboxes = {}
        for plat_key, ps in PLATFORM_STYLES.items():
            cb = QCheckBox(ps["label"])
            cb.setChecked(True)
            cb.setStyleSheet(f"""
                QCheckBox {{
                    color: {ps['accent']};
                    font-size: 12px;
                    font-weight: 500;
                    spacing: 6px;
                }}
                QCheckBox::indicator {{
                    width: 15px;
                    height: 15px;
                    border-radius: 3px;
                    border: 1px solid {ps['accent']};
                    background: {COLORS['bg_input']};
                }}
                QCheckBox::indicator:checked {{
                    background: {ps['accent']};
                }}
            """)
            cb.stateChanged.connect(self._on_platform_selection_changed)
            plat_row.addWidget(cb)
            self.plat_checkboxes[plat_key] = cb

        plat_row.addStretch()

        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"font-size: 12px; color: {COLORS['accent_green']}; font-weight: 600;")
        plat_row.addWidget(self.status_label)

        self.clear_btn = QPushButton("Clear Selection")
        self.clear_btn.setStyleSheet(btn_style(COLORS['bg_input'], COLORS['border'], COLORS['text_muted'], padding="4px 10px", radius=5))
        self.clear_btn.setVisible(False)
        self.clear_btn.clicked.connect(self._on_clear)
        plat_row.addWidget(self.clear_btn)

        main_layout.addLayout(plat_row)

    def _apply_style(self, drag_over: bool):
        if drag_over:
            self.setStyleSheet(f"""
                VideoDropZone {{
                    background: {COLORS['accent_blue']}18;
                    border: 2px dashed {COLORS['accent_blue']};
                    border-radius: 10px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                VideoDropZone {{
                    background: {COLORS['bg_card']};
                    border: 2px dashed {COLORS['border']};
                    border-radius: 10px;
                }}
            """)

    def get_selected_platforms(self):
        return [k for k, cb in self.plat_checkboxes.items() if cb.isChecked()]

    def _on_platform_selection_changed(self):
        if self._selected_files:
            self.files_selected.emit(self._selected_files, self.get_selected_platforms())

    def _on_browse(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Video Files to Upload",
            "",
            "Video Files (*.mp4 *.mov *.mkv *.avi *.webm);;All Files (*.*)",
        )
        if files:
            self.add_files(files)

    def add_files(self, paths):
        valid = [p for p in paths if os.path.isfile(p) and p.lower().endswith(SUPPORTED_VIDEO_EXTS)]
        if not valid:
            return
        for p in valid:
            if p not in self._selected_files:
                self._selected_files.append(p)
        count = len(self._selected_files)
        names = ", ".join(os.path.basename(p) for p in self._selected_files[-2:])
        if count > 2:
            names += f" (+{count - 2} more)"
        self.status_label.setText(f"✓ {count} video{'s' if count != 1 else ''} staged: {names}")
        self.clear_btn.setVisible(True)
        self.files_selected.emit(self._selected_files, self.get_selected_platforms())

    def _on_clear(self):
        self._selected_files.clear()
        self.status_label.setText("")
        self.clear_btn.setVisible(False)
        self.cleared.emit()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(u.toLocalFile().lower().endswith(SUPPORTED_VIDEO_EXTS) for u in urls):
                event.acceptProposedAction()
                self._apply_style(True)
                return
        event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self._apply_style(False)

    def dropEvent(self, event):
        self._apply_style(False)
        paths = []
        if event.mimeData().hasUrls():
            for u in event.mimeData().urls():
                fp = u.toLocalFile()
                if fp.lower().endswith(SUPPORTED_VIDEO_EXTS) and os.path.isfile(fp):
                    paths.append(fp)
        if paths:
            event.acceptProposedAction()
            self.add_files(paths)
        else:
            event.ignore()


class AvailableVideosListWidget(QListWidget):
    """List of available / discovered videos in 'Ready to Upload'. Drag items down into 'Want to Upload'."""
    item_staged = pyqtSignal(str, str)  # (path, label)

    def __init__(self, platform: str, accent: str, parent=None):
        super().__init__(parent)
        self.platform = platform
        self.accent = accent
        self.setDragEnabled(True)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.itemDoubleClicked.connect(self._on_double_click)

    def _on_double_click(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        label = item.text()
        if path:
            self.item_staged.emit(path, label)

    def _show_context_menu(self, pos):
        item = self.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {COLORS['bg_card']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 18px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: {self.accent}33;
                color: {COLORS['text_primary']};
            }}
        """)
        stage_action = menu.addAction("⬇ Move to 'Want to Upload'")
        menu.addSeparator()
        preview_action = menu.addAction("▶ Preview Video Locally")
        copy_action = menu.addAction("📋 Copy File Path")

        action = menu.exec(self.mapToGlobal(pos))
        path = item.data(Qt.ItemDataRole.UserRole)
        if action == stage_action and path:
            self.item_staged.emit(path, item.text())
        elif action == preview_action and path and os.path.exists(path):
            os.startfile(path)
        elif action == copy_action and path:
            QApplication.clipboard().setText(path)

    def startDrag(self, supportedActions):
        items = self.selectedItems()
        if not items:
            return

        drag = QDrag(self)
        mime_data = QMimeData()

        urls = []
        paths = []
        entries = []
        for item in items:
            p = item.data(Qt.ItemDataRole.UserRole)
            if p and os.path.isfile(p):
                paths.append(p)
                urls.append(QUrl.fromLocalFile(p))
                entries.append({"path": p, "label": item.text()})

        if urls:
            mime_data.setUrls(urls)

        payload = {
            "source_type": "available",
            "source_platform": self.platform,
            "entries": entries,
            "paths": paths,
        }
        mime_data.setData("application/x-ai-video-manager-item", json.dumps(payload).encode("utf-8"))
        mime_data.setText("\n".join(paths))

        drag.setMimeData(mime_data)
        drag.exec(Qt.DropAction.CopyAction | Qt.DropAction.MoveAction)


class WantUploadListWidget(QListWidget):
    """
    Staging list for 'Want to Upload'.
    ONLY videos placed here will be uploaded when the user clicks Upload!
    Supports:
    - Drag & drop from 'Ready to Upload' above
    - Drag & drop reordering (priority order)
    - Drag & drop across platform columns
    - Dropping video files directly from Windows Explorer
    - Double-click to unstage back to 'Ready to Upload'
    - Delete/Backspace to unstage
    """
    order_changed = pyqtSignal()
    item_unstaged = pyqtSignal(str)  # path

    def __init__(self, platform: str, accent: str, parent=None):
        super().__init__(parent)
        self.platform = platform
        self.accent = accent
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDropIndicatorShown(True)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.itemDoubleClicked.connect(self._on_double_click)

    def _on_double_click(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            self.item_unstaged.emit(path)

    def _show_context_menu(self, pos):
        item = self.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {COLORS['bg_card']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 18px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: {self.accent}33;
                color: {COLORS['text_primary']};
            }}
        """)
        unstage_action = menu.addAction("⬆ Unstage (Back to Ready to Upload)")
        menu.addSeparator()
        preview_action = menu.addAction("▶ Preview Video Locally")
        copy_action = menu.addAction("📋 Copy File Path")

        action = menu.exec(self.mapToGlobal(pos))
        path = item.data(Qt.ItemDataRole.UserRole)
        if action == unstage_action and path:
            self.item_unstaged.emit(path)
        elif action == preview_action and path and os.path.exists(path):
            os.startfile(path)
        elif action == copy_action and path:
            QApplication.clipboard().setText(path)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            items = self.selectedItems()
            if items:
                for itm in items:
                    p = itm.data(Qt.ItemDataRole.UserRole)
                    if p:
                        self.item_unstaged.emit(p)
                return
        super().keyPressEvent(event)

    def startDrag(self, supportedActions):
        items = self.selectedItems()
        if not items:
            return

        drag = QDrag(self)
        mime_data = QMimeData()

        urls = []
        paths = []
        entries = []
        for item in items:
            p = item.data(Qt.ItemDataRole.UserRole)
            if p and os.path.isfile(p):
                paths.append(p)
                urls.append(QUrl.fromLocalFile(p))
                entries.append({"path": p, "label": item.text()})

        if urls:
            mime_data.setUrls(urls)

        payload = {
            "source_type": "want",
            "source_platform": self.platform,
            "entries": entries,
            "paths": paths,
        }
        mime_data.setData("application/x-ai-video-manager-item", json.dumps(payload).encode("utf-8"))
        mime_data.setText("\n".join(paths))

        drag.setMimeData(mime_data)
        drag.exec(Qt.DropAction.MoveAction | Qt.DropAction.CopyAction)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-ai-video-manager-item"):
            event.acceptProposedAction()
            return
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(u.toLocalFile().lower().endswith(SUPPORTED_VIDEO_EXTS) for u in urls):
                event.acceptProposedAction()
                return
        event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-ai-video-manager-item") or event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        # 1. Internal drag from this list, available list, or another platform
        if event.mimeData().hasFormat("application/x-ai-video-manager-item"):
            try:
                raw = event.mimeData().data("application/x-ai-video-manager-item").data().decode("utf-8")
                data = json.loads(raw)
                src_type = data.get("source_type")
                src_platform = data.get("source_platform")
                entries = data.get("entries", [])
                paths = data.get("paths", [])

                if src_type == "want" and src_platform == self.platform and event.source() == self:
                    # Reordering items within the same 'Want to Upload' list
                    pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
                    target_item = self.itemAt(pos)

                    selected_items = self.selectedItems()
                    if not selected_items or target_item in selected_items:
                        event.acceptProposedAction()
                        return

                    item_data = []
                    for itm in selected_items:
                        item_data.append((
                            itm.text(),
                            itm.data(Qt.ItemDataRole.UserRole),
                            itm.toolTip(),
                            itm.foreground(),
                        ))

                    for itm in selected_items:
                        r = self.row(itm)
                        if r != -1:
                            self.takeItem(r)

                    if target_item:
                        target_row = self.row(target_item)
                        if target_row == -1:
                            target_row = self.count()
                    else:
                        target_row = self.count()

                    for text, path, tt, fg in item_data:
                        new_item = QListWidgetItem(text)
                        new_item.setData(Qt.ItemDataRole.UserRole, path)
                        new_item.setToolTip(tt)
                        new_item.setForeground(fg)
                        self.insertItem(target_row, new_item)
                        new_item.setSelected(True)
                        target_row += 1

                    event.acceptProposedAction()
                    self.order_changed.emit()
                    return
                else:
                    # Dropped from 'Ready to Upload' or from another platform's column!
                    panel = self.parent()
                    while panel and not hasattr(panel, "stage_video"):
                        panel = panel.parent()
                    if panel:
                        for entry in entries:
                            panel.stage_video(entry["path"], entry.get("label"))
                    event.acceptProposedAction()
                    self.order_changed.emit()
                    return
            except Exception as e:
                log.warning("Drop error: %s", e)

        # 2. External video file(s) dropped from Windows Explorer
        paths = []
        if event.mimeData().hasUrls():
            for u in event.mimeData().urls():
                fp = u.toLocalFile()
                if fp.lower().endswith(SUPPORTED_VIDEO_EXTS) and os.path.isfile(fp):
                    paths.append(fp)

        if paths:
            event.acceptProposedAction()
            panel = self.parent()
            while panel and not hasattr(panel, "stage_video"):
                panel = panel.parent()
            if panel:
                for p in paths:
                    panel.stage_video(p)
            self.order_changed.emit()
        else:
            event.ignore()


class _PlatformPanel(QFrame):
    """
    Self-contained upload panel for one platform.
    Layout strictly adheres to:
    1. Ready to upload (available library)
    2. want to upload (staging queue)
    3. upload button (uploads ONLY staged items!)
    4. live (uploaded & completed live videos)
    """

    def __init__(self, platform, queue, config, load_title_fn, load_desc_fn, load_meta_fn=None, upload_tab=None, parent=None):
        super().__init__(parent)
        self.platform = platform
        self.queue = queue
        self.config = config
        self._load_title_fn = load_title_fn
        self._load_desc_fn = load_desc_fn
        self._load_meta_fn = load_meta_fn
        self.upload_tab = upload_tab
        self._staged_videos = {}  # {vpath: label}
        self._available_cache = []

        ps = PLATFORM_STYLES[platform]
        accent = ps["accent"]
        accent_hover = ps["accent_hover"]

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(f"""
            _PlatformPanel {{
                background: {accent}08;
                border: 1px solid {accent}40;
                border-radius: 10px;
            }}
        """)

        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        # Platform Header
        header = QLabel(ps["label"])
        header.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {accent};")
        layout.addWidget(header)

        # ----------------------------------------------------
        # 1. Ready to Upload (Available Library)
        # ----------------------------------------------------
        self.available_group = QGroupBox("Ready to Upload")
        self.available_group.setStyleSheet(f"""
            QGroupBox {{
                background: {COLORS['bg_card']}; border: 1px solid {COLORS['border']};
                border-radius: 8px; padding: 10px; margin-top: 8px;
                font-size: 12px; font-weight: 600; color: {COLORS['text_muted']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin; subcontrol-position: top left;
                padding: 2px 8px;
            }}
        """)
        avail_layout = QVBoxLayout()
        avail_layout.setContentsMargins(0, 4, 0, 0)
        avail_layout.setSpacing(6)

        self.available_list = AvailableVideosListWidget(self.platform, accent, parent=self)
        self.available_list.setStyleSheet(f"""
            QListWidget {{
                background: {COLORS['bg_medium']}; color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']}; border-radius: 6px;
            }}
            QListWidget::item {{ padding: 6px 8px; font-size: 12px; }}
            QListWidget::item:selected {{ background: {accent}33; }}
            QListWidget::item:hover {{ background: {COLORS['bg_input']}; }}
        """)
        self.available_list.item_staged.connect(self.stage_video)
        avail_layout.addWidget(self.available_list)

        # Quick Stage Controls
        avail_btn_row = QHBoxLayout()
        avail_btn_row.setSpacing(6)
        self.stage_sel_btn = QPushButton("⬇ Stage Selected")
        self.stage_sel_btn.setStyleSheet(btn_style(COLORS['bg_input'], COLORS['border'], COLORS['text_primary'], padding="4px 8px", radius=4))
        self.stage_sel_btn.clicked.connect(self._stage_selected)
        avail_btn_row.addWidget(self.stage_sel_btn)

        self.stage_all_btn = QPushButton("⬇ Stage All")
        self.stage_all_btn.setStyleSheet(btn_style(COLORS['bg_input'], COLORS['border'], COLORS['text_muted'], padding="4px 8px", radius=4))
        self.stage_all_btn.clicked.connect(self._stage_all)
        avail_btn_row.addWidget(self.stage_all_btn)
        avail_layout.addLayout(avail_btn_row)

        self.available_group.setLayout(avail_layout)
        layout.addWidget(self.available_group)

        # ----------------------------------------------------
        # 2. Want to Upload (Staging Queue)
        # ----------------------------------------------------
        self.want_group = QGroupBox("Want to Upload (0)")
        self.want_group.setStyleSheet(f"""
            QGroupBox {{
                background: {accent}0a; border: 1.5px dashed {accent}88;
                border-radius: 8px; padding: 10px; margin-top: 8px;
                font-size: 12px; font-weight: bold; color: {accent};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin; subcontrol-position: top left;
                padding: 2px 8px;
            }}
        """)
        want_layout = QVBoxLayout()
        want_layout.setContentsMargins(0, 4, 0, 0)
        want_layout.setSpacing(6)

        self.want_list = WantUploadListWidget(self.platform, accent, parent=self)
        self.want_list.setStyleSheet(f"""
            QListWidget {{
                background: {COLORS['bg_medium']}; color: {COLORS['text_primary']};
                border: 1px solid {accent}44; border-radius: 6px;
            }}
            QListWidget::item {{ padding: 6px 8px; font-size: 12px; }}
            QListWidget::item:selected {{ background: {accent}55; }}
            QListWidget::item:hover {{ background: {COLORS['bg_input']}; }}
        """)
        self.want_list.item_unstaged.connect(self.unstage_video)
        self.want_list.order_changed.connect(self._on_want_order_changed)
        want_layout.addWidget(self.want_list)

        # Quick Unstage Controls
        want_btn_row = QHBoxLayout()
        want_btn_row.setSpacing(6)
        self.unstage_sel_btn = QPushButton("⬆ Unstage Selected")
        self.unstage_sel_btn.setStyleSheet(btn_style(COLORS['bg_input'], COLORS['border'], COLORS['text_primary'], padding="4px 8px", radius=4))
        self.unstage_sel_btn.clicked.connect(self._unstage_selected)
        want_btn_row.addWidget(self.unstage_sel_btn)

        self.clear_want_btn = QPushButton("✖ Clear Queue")
        self.clear_want_btn.setStyleSheet(btn_style(COLORS['bg_input'], COLORS['border'], COLORS['text_muted'], padding="4px 8px", radius=4))
        self.clear_want_btn.clicked.connect(self._unstage_all)
        want_btn_row.addWidget(self.clear_want_btn)
        want_layout.addLayout(want_btn_row)

        self.want_group.setLayout(want_layout)
        layout.addWidget(self.want_group)

        # ----------------------------------------------------
        # 3. Upload Button (Uploads ONLY Staged Items!)
        # ----------------------------------------------------
        self.upload_btn = QPushButton(f"Upload to {ps['short_label']} (0)")
        self.upload_btn.setStyleSheet(btn_style(accent, accent_hover, "white", padding="10px 14px", radius=6))
        self.upload_btn.setToolTip(f"Upload only the videos currently staged in 'Want to Upload' to {ps['label']}")
        self.upload_btn.clicked.connect(self._upload)
        layout.addWidget(self.upload_btn)

        if self.platform == "facebook":
            self.meta_biz_btn = QPushButton("Post via Business Suite 🌐")
            self.meta_biz_btn.setStyleSheet(btn_style(COLORS['bg_input'], COLORS['border'], COLORS['text_primary'], padding="6px 12px", radius=6))
            self.meta_biz_btn.setToolTip("Opens Meta Business Suite with staged video selected and title/description copied to clipboard!")
            self.meta_biz_btn.clicked.connect(self._open_business_suite)
            layout.addWidget(self.meta_biz_btn)

        # ----------------------------------------------------
        # 4. Uploaded & Live
        # ----------------------------------------------------
        self.progress_group = QGroupBox("Uploaded & Live")
        self.progress_group.setStyleSheet(f"""
            QGroupBox {{
                background: {COLORS['bg_card']}; border: 1px solid {COLORS['border']};
                border-radius: 8px; padding: 10px; margin-top: 8px;
                font-size: 12px; font-weight: 600; color: {COLORS['text_muted']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin; subcontrol-position: top left;
                padding: 2px 8px;
            }}
        """)
        progress_inner = QVBoxLayout()
        progress_inner.setContentsMargins(0, 4, 0, 0)

        self.progress_list = QListWidget()
        self.progress_list.setStyleSheet(f"""
            QListWidget {{
                background: {COLORS['bg_medium']}; color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']}; border-radius: 6px;
            }}
            QListWidget::item {{ padding: 6px 8px; font-size: 11px; }}
            QListWidget::item:hover {{ background: {COLORS['bg_input']}; }}
        """)
        self.progress_list.itemDoubleClicked.connect(self._open_upload_link)
        progress_inner.addWidget(self.progress_list)
        self.progress_group.setLayout(progress_inner)
        layout.addWidget(self.progress_group)

        self.setLayout(layout)

    # ---------------- Staging Logic ----------------
    def stage_video(self, vpath: str, label: str = None):
        """Move a video into 'Want to Upload'."""
        if not vpath or not os.path.exists(vpath):
            return
        if not label:
            label = f"📁 {os.path.basename(vpath)}"

        # Check if already in want_list
        for i in range(self.want_list.count()):
            if self.want_list.item(i).data(Qt.ItemDataRole.UserRole) == vpath:
                return

        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, vpath)
        item.setToolTip(f"File: {os.path.basename(vpath)}\n• Staged for upload to {self.platform.title()}\n• Drag to reorder priority\n• Double-click to unstage")
        self.want_list.addItem(item)
        self._staged_videos[vpath] = label

        # Remove from available list if present
        for i in range(self.available_list.count()):
            if self.available_list.item(i).data(Qt.ItemDataRole.UserRole) == vpath:
                self.available_list.takeItem(i)
                break

        self._update_counts()

    def unstage_video(self, vpath: str):
        """Remove a video from 'Want to Upload' and return it to 'Ready to Upload'."""
        label = self._staged_videos.pop(vpath, None)

        for i in range(self.want_list.count()):
            if self.want_list.item(i).data(Qt.ItemDataRole.UserRole) == vpath:
                self.want_list.takeItem(i)
                break

        # Re-add to available list if matching cache
        if self._available_cache:
            for itm in self._available_cache:
                c_label, c_path = itm[0], itm[1]
                if c_path == vpath:
                    label = c_label
                    break

        if label:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, vpath)
            item.setToolTip(f"File: {os.path.basename(vpath)}\nDouble-click or drag down to stage into 'Want to Upload'")
            self.available_list.addItem(item)

        self._update_counts()

    def _stage_selected(self):
        items = self.available_list.selectedItems()
        for itm in items:
            p = itm.data(Qt.ItemDataRole.UserRole)
            if p:
                self.stage_video(p, itm.text())

    def _stage_all(self):
        while self.available_list.count() > 0:
            itm = self.available_list.item(0)
            p = itm.data(Qt.ItemDataRole.UserRole)
            lbl = itm.text()
            self.stage_video(p, lbl)

    def _unstage_selected(self):
        items = self.want_list.selectedItems()
        for itm in items:
            p = itm.data(Qt.ItemDataRole.UserRole)
            if p:
                self.unstage_video(p)

    def _unstage_all(self):
        paths = [self.want_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.want_list.count())]
        for p in paths:
            if p:
                self.unstage_video(p)

    def _on_want_order_changed(self):
        self._update_counts()

    def _update_counts(self):
        ps = PLATFORM_STYLES[self.platform]
        cnt = self.want_list.count()
        self.want_group.setTitle(f"Want to Upload ({cnt})")
        self.upload_btn.setText(f"Upload to {ps['short_label']} ({cnt})")
        self.available_group.setTitle(f"Ready to Upload ({self.available_list.count()})")

    # ---------------- Refresh & Sync ----------------
    def refresh_pending(self, videos):
        from app import upload_registry
        self._available_cache = videos

        # Current staged paths
        staged_paths = {self.want_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.want_list.count())}

        self.available_list.clear()

        for itm in videos:
            if len(itm) == 3:
                label, vpath, target_plats = itm
                if target_plats and self.platform not in target_plats:
                    continue
            else:
                label, vpath = itm

            # If already in Want to Upload, don't show in Ready to Upload
            if vpath in staged_paths:
                continue

            # Check if completed/live in Video Manager or Queue
            already = any(
                t.type == TaskType.UPLOAD_VIDEO
                and t.params.get("video_path") == vpath
                and t.params.get("platform") == self.platform
                and t.status.value == "completed"
                for t in self.queue.get_tasks()
            )
            if not already:
                try:
                    already = upload_registry.find_existing(vpath, platform=self.platform) is not None
                except Exception:
                    pass

            if already:
                continue

            already_running = any(
                t.type == TaskType.UPLOAD_VIDEO
                and t.params.get("video_path") == vpath
                and t.params.get("platform") == self.platform
                and t.status.value in ("pending", "running")
                for t in self.queue.get_tasks()
            )

            other_plats = upload_registry.get_platforms_for_video(vpath)
            badges = []
            if "youtube" in other_plats or "youtube_short" in other_plats:
                badges.append("YT ✅")
            if "facebook" in other_plats:
                badges.append("FB ✅")
            if "tiktok" in other_plats:
                badges.append("TT ✅")

            display_text = label
            if badges:
                display_text = f"{label}  [{' '.join(badges)}]"

            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, vpath)
            if already_running:
                item.setForeground(Qt.GlobalColor.gray)
                item.setToolTip("Upload in progress in queue...")
            else:
                tt = f"File: {os.path.basename(vpath)}\nStatus: Ready in Library"
                if badges:
                    tt += f"\nAlready uploaded to: {', '.join(badges)}"
                tt += "\n• Double-click or drag down into 'Want to Upload'"
                item.setToolTip(tt)

            self.available_list.addItem(item)

        self._update_counts()

    def refresh_progress(self, tasks):
        from app import upload_registry
        self.progress_list.clear()

        # 1. Active or queued tasks
        platform_tasks = [t for t in tasks if t.params.get("platform") == self.platform]
        for t in platform_tasks[-10:]:
            title = t.title[:35]
            status = t.status.value
            progress = t.progress
            step = t.step_name or ""
            err = getattr(t, "error", "") or ""

            if status == "running":
                info = f"⚡ {title} ({progress}%)"
                if step:
                    info += f" | {step[:40]}"
                item = QListWidgetItem(info)
                item.setForeground(QColor(COLORS["accent_blue"]))
                self.progress_list.addItem(item)
            elif status == "failed" and err:
                short_err = err.strip().split("\n")[0][:60]
                item = QListWidgetItem(f"❌ {title} - Failed: {short_err}")
                item.setToolTip(f"Error: {err}")
                item.setForeground(Qt.GlobalColor.red)
                self.progress_list.addItem(item)

        # 2. Uploaded items from uploads.json
        uploaded = upload_registry.get_uploaded_items_for_platform(self.platform)
        for it in uploaded[:30]:
            url = it.get("url") or ""
            vpath = it.get("path") or ""
            base_fname = os.path.basename(vpath) if vpath and not vpath.startswith("http") else ""
            metrics = it.get("metrics") or {}
            title = metrics.get("title") or it.get("title") or base_fname or "Uploaded Video"
            if len(title) > 36:
                title = title[:36] + "..."

            views = metrics.get("views_str")
            views_part = f" • 👁️ {views}" if views and views != "--" else ""
            is_deleted = metrics.get("status") == "Not Found / Deleted"

            tag = "⚠️ (Removed)" if is_deleted else "✅"
            item = QListWidgetItem(f"{tag} {title}{views_part}")
            if is_deleted:
                item.setForeground(QColor(COLORS["text_muted"]))
            else:
                item.setForeground(QColor(COLORS["accent_green"]))

            if url:
                item.setData(Qt.ItemDataRole.UserRole, url)
                tt = f"Title: {title}\nPlatform: {self.platform.title()}\nLive URL: {url}"
                if views:
                    tt += f"\nLive Views: {views}"
                tt += "\nDouble-click to open in browser"
                item.setToolTip(tt)

            self.progress_list.addItem(item)

        self.progress_group.setTitle(f"Uploaded & Live ({len(uploaded)})")

    def _open_upload_link(self, item):
        url = item.data(Qt.ItemDataRole.UserRole)
        if url and url.startswith("http"):
            import webbrowser
            webbrowser.open(url)

    def _open_business_suite(self):
        import subprocess, webbrowser
        cur_item = self.want_list.currentItem() or self.available_list.currentItem()
        vpath = cur_item.data(Qt.ItemDataRole.UserRole) if cur_item else None
        if vpath and os.path.exists(vpath):
            title = self._load_title_fn(vpath) or os.path.basename(vpath).replace(
                "_shorts.mp4", "").replace("_video.mp4", "").replace("_", " ").title()
            desc = self._load_desc_fn(vpath) or title
            clipboard_text = f"{title}\n\n{desc}\n\n#reels #viral #shorts"
            QApplication.clipboard().setText(clipboard_text)
            subprocess.run(f'explorer /select,"{vpath}"', shell=True)
        webbrowser.open("https://business.facebook.com/latest/reels_composer")

    # ---------------- Upload Execution ----------------
    def _upload(self):
        """Uploads ONLY items staged in 'Want to Upload'."""
        videos = []
        for i in range(self.want_list.count()):
            item = self.want_list.item(i)
            path = item.data(Qt.ItemDataRole.UserRole)
            if path and os.path.isfile(path):
                videos.append(path)

        if not videos:
            QMessageBox.information(
                self,
                "Nothing Staged to Upload",
                f"No videos are in the 'Want to Upload' queue for {self.platform.title()}.\n\n"
                "Drag videos down from 'Ready to Upload' above or drop files into the box first!",
            )
            return

        for path in videos:
            title = self._load_title_fn(path)
            if not title:
                base = os.path.basename(path)
                for ext in SUPPORTED_VIDEO_EXTS:
                    if base.lower().endswith(ext):
                        base = base[:-len(ext)]
                        break
                base = base.replace("_shorts", "").replace("_video", "").replace("_", " ").replace("-", " ")
                title = base.strip().title()

            description = self._load_desc_fn(path) or f"AI-generated video - {title}"
            tags = ["ai", "automated", "video"]
            if self._load_meta_fn:
                meta = self._load_meta_fn(path)
                if meta and meta.get("tags"):
                    tags = meta["tags"]

            thumb_path = None
            cand = os.path.join(os.path.dirname(path), "thumbnail.jpg")
            if os.path.exists(cand):
                thumb_path = cand

            self.queue.add_task(
                TaskType.UPLOAD_VIDEO,
                {
                    "video_path": path,
                    "thumbnail_path": thumb_path,
                    "title": title,
                    "description": description,
                    "tags": tags,
                    "platform": self.platform,
                },
                f"Upload to {self.platform}: {title[:30]}",
            )

        # Clear staged list after queueing
        self.want_list.clear()
        self._staged_videos.clear()
        self._update_counts()


class UploadTab(QWidget):
    def __init__(self, queue_manager, config, main_window=None, parent=None):
        super().__init__(parent)
        self.queue = queue_manager
        self.config = config
        self.main_window = main_window

        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        header_layout = QHBoxLayout()
        header = QLabel("Upload Manager")
        header.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {COLORS['text_primary']};")
        header_layout.addWidget(header)

        header_layout.addStretch()

        self.auto_upload_check = QCheckBox("Auto-Upload")
        self.auto_upload_check.setChecked(config.get("auto_upload", False))
        self.auto_upload_check.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 13px;")
        self.auto_upload_check.stateChanged.connect(self._on_auto_upload_changed)
        header_layout.addWidget(self.auto_upload_check)

        scan_btn = QPushButton("Scan for Videos")
        scan_btn.setStyleSheet(btn_style(COLORS['bg_input'], COLORS['border'], COLORS['text_secondary']))
        scan_btn.clicked.connect(self._refresh_pending)
        header_layout.addWidget(scan_btn)

        cancel_all_btn = QPushButton("Cancel All")
        cancel_all_btn.setStyleSheet(btn_style(COLORS['accent_red'], COLORS['accent_red_hover'], "white"))
        cancel_all_btn.clicked.connect(self._cancel_all_uploads)
        header_layout.addWidget(cancel_all_btn)

        upload_all_btn = QPushButton("Upload All Staged")
        upload_all_btn.setStyleSheet(btn_style(COLORS['accent_green'], COLORS['accent_green_hover']))
        upload_all_btn.setToolTip("Upload all videos currently staged in 'Want to Upload' across all 4 platforms")
        upload_all_btn.clicked.connect(self._upload_all)
        header_layout.addWidget(upload_all_btn)

        layout.addLayout(header_layout)

        # Top Drag and Drop Zone
        self.drop_zone = VideoDropZone(self)
        self.drop_zone.files_selected.connect(self._on_drop_zone_files)
        self.drop_zone.upload_all_requested.connect(self._upload_all)
        self.drop_zone.cleared.connect(self._on_drop_zone_cleared)
        layout.addWidget(self.drop_zone)

        # 4 Platform Splitter Columns
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.fb_panel = _PlatformPanel(
            "facebook", self.queue, self.config,
            self._load_youtube_title, self._load_full_description,
            self._load_meta_common, upload_tab=self,
        )
        self.yt_panel = _PlatformPanel(
            "youtube", self.queue, self.config,
            self._load_youtube_title, self._load_full_description,
            self._load_meta_common, upload_tab=self,
        )
        self.yt_short_panel = _PlatformPanel(
            "youtube_short", self.queue, self.config,
            self._load_youtube_title, self._load_full_description,
            self._load_meta_common, upload_tab=self,
        )
        self.tiktok_panel = _PlatformPanel(
            "tiktok", self.queue, self.config,
            self._load_youtube_title, self._load_full_description,
            self._load_meta_common, upload_tab=self,
        )

        splitter.addWidget(self.fb_panel)
        splitter.addWidget(self.yt_panel)
        splitter.addWidget(self.yt_short_panel)
        splitter.addWidget(self.tiktok_panel)
        splitter.setSizes([260, 260, 260, 260])

        layout.addWidget(splitter)
        self.setLayout(layout)

        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self._refresh_upload_progress)
        self._refresh_timer.start(2500)

        self._pending_timer = QTimer()
        self._pending_timer.timeout.connect(self._refresh_pending)
        self._pending_timer.start(8000)

        self._refresh_pending()

    def _on_drop_zone_files(self, paths, platforms):
        plat_map = {
            "facebook": self.fb_panel,
            "youtube": self.yt_panel,
            "youtube_short": self.yt_short_panel,
            "tiktok": self.tiktok_panel,
        }
        for pl in platforms:
            panel = plat_map.get(pl)
            if panel:
                for p in paths:
                    panel.stage_video(p)

    def _on_drop_zone_cleared(self):
        pass

    def _refresh_pending(self):
        try:
            self._do_refresh_pending()
        except Exception as e:
            log.warning("_refresh_pending error: %s", e)
            import traceback
            log.warning(traceback.format_exc())

    def _discover_videos(self):
        videos = []
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        manhwa_root = os.path.join(project_root, "projects", "manhwa_engine", "output", "Final")
        if os.path.isdir(manhwa_root):
            for entry in sorted(os.listdir(manhwa_root)):
                if entry.startswith("ch") and os.path.isdir(os.path.join(manhwa_root, entry)):
                    ch_dir = os.path.join(manhwa_root, entry)
                    for f in sorted(os.listdir(ch_dir)):
                        if f.endswith("_video.mp4") and not f.startswith("panel_") and not f.startswith("title_"):
                            vpath = os.path.join(ch_dir, f)
                            if os.path.getsize(vpath) > 1024:
                                label = "[Manhwa] Chapter {}".format(entry[2:].lstrip("0") or entry[2:])
                                videos.append((label, vpath))

        anime_root = os.path.join(project_root, "projects", "anime_engine", "output", "shorts")
        if os.path.isdir(anime_root):
            for f in sorted(os.listdir(anime_root)):
                if f.endswith("_shorts.mp4"):
                    vpath = os.path.join(anime_root, f)
                    if os.path.getsize(vpath) > 1024:
                        videos.append((f"[Anime] {f[:40]}", vpath))

        mc_root = os.path.join(project_root, "projects", "minecraft_engine", "output")
        if os.path.isdir(mc_root):
            for f in sorted(os.listdir(mc_root)):
                if f.endswith(".mp4") and "story_" in f:
                    vpath = os.path.join(mc_root, f)
                    if os.path.getsize(vpath) > 1024:
                        videos.append((f"[Minecraft] {f}", vpath))

        movie_root = os.path.join(project_root, "projects", "moviereels_engine", "output")
        if os.path.isdir(movie_root):
            for f in sorted(os.listdir(movie_root)):
                if f.endswith(".mp4") and not f.startswith("_") and not f.endswith("_raw.mp4"):
                    vpath = os.path.join(movie_root, f)
                    if os.path.getsize(vpath) > 1024:
                        label = "[Movie] {}".format(f.replace(".mp4", "").replace("_", " ").title()[:50])
                        videos.append((label, vpath))

        return videos

    def _do_refresh_pending(self):
        videos = self._discover_videos()
        self.fb_panel.refresh_pending(videos)
        self.yt_panel.refresh_pending(videos)
        self.yt_short_panel.refresh_pending(videos)
        self.tiktok_panel.refresh_pending(videos)

    def _refresh_upload_progress(self):
        tasks = self.queue.get_tasks()
        self.fb_panel.refresh_progress(tasks)
        self.yt_panel.refresh_progress(tasks)
        self.yt_short_panel.refresh_progress(tasks)
        self.tiktok_panel.refresh_progress(tasks)

    def _load_meta_common(self, video_path):
        """Load metadata from any supported source."""
        ch_dir = os.path.dirname(video_path)

        mc_meta = os.path.join(ch_dir, os.path.splitext(os.path.basename(video_path))[0] + "_meta.json")
        if os.path.isfile(mc_meta):
            try:
                with open(mc_meta, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

        meta_path = os.path.join(ch_dir, "youtube_meta.json")
        if os.path.isfile(meta_path):
            try:
                with open(meta_path, encoding="utf-8") as f:
                    meta = json.load(f)
                if meta.get("title") or meta.get("description"):
                    return meta
            except Exception:
                pass

        return None

    def _load_full_description(self, video_path):
        meta = self._load_meta_common(video_path)
        if meta and meta.get("description"):
            return meta["description"]

        ch_dir = os.path.dirname(video_path)
        desc_file = os.path.join(ch_dir, "youtube_description.txt")
        if os.path.isfile(desc_file):
            try:
                with open(desc_file, encoding="utf-8") as f:
                    return f.read().strip()
            except Exception:
                pass
        try:
            from upload.youtube_uploader import resolve_manhwa_metadata
            _, desc = resolve_manhwa_metadata(video_path, self.config)
            if desc:
                return desc
        except Exception:
            pass
        return ""

    def _load_youtube_title(self, video_path):
        meta = self._load_meta_common(video_path)
        if meta and meta.get("title"):
            return meta["title"]

        ch_dir = os.path.dirname(video_path)
        desc_path = os.path.join(ch_dir, "youtube_description.txt")
        try:
            if os.path.isfile(desc_path):
                with open(desc_path, encoding="utf-8") as f:
                    txt = f.read()
                if "TITLE:" in txt:
                    after = txt.split("TITLE:", 1)[1]
                    line = after.strip().splitlines()[0].strip()
                    if line:
                        return line
                for ln in txt.splitlines():
                    ln = ln.strip()
                    if ln:
                        return ln
        except Exception:
            pass
        try:
            from upload.youtube_uploader import resolve_manhwa_metadata
            title, _ = resolve_manhwa_metadata(video_path, self.config)
            if title:
                return title
        except Exception:
            pass
        try:
            import re
            dn = os.path.basename(os.path.dirname(video_path))
            m = re.search(r"ch(\d+)", dn)
            if m:
                ch = int(m.group(1))
                project_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                             self.config.get("manhwa_project_path", "projects/manhwa_engine"))
                bible_path = os.path.join(project_path, "story_bible.json")
                if os.path.isfile(bible_path):
                    with open(bible_path, encoding="utf-8") as f:
                        bible = json.load(f)
                    series = bible.get("title", "Manhwa").strip()
                    ch_info = next((c for c in bible.get("chapters", []) if c.get("number") == ch), None)
                    ch_name = (ch_info.get("title") or "").strip() if ch_info else ""
                    if ch_name:
                        return f"{series} | Chapter {ch}: {ch_name} (Manhwa Motion Comic)"
                    return f"{series} | Chapter {ch} (Manhwa Motion Comic)"
        except Exception:
            pass
        return None

    def _cancel_all_uploads(self):
        for t in self.queue.get_tasks():
            if t.type == TaskType.UPLOAD_VIDEO and t.status.value in ("pending", "running"):
                self.queue.cancel_task(t.id)

    def _upload_all(self):
        """Uploads all staged items across all 4 platforms."""
        total_staged = (
            self.fb_panel.want_list.count() +
            self.yt_panel.want_list.count() +
            self.yt_short_panel.want_list.count() +
            self.tiktok_panel.want_list.count()
        )
        if total_staged == 0:
            QMessageBox.information(
                self,
                "Nothing Staged to Upload",
                "There are no videos staged in 'Want to Upload' in any column.\n\n"
                "Drag videos down into 'Want to Upload' or drop video files into the box first!",
            )
            return

        self.fb_panel._upload()
        self.yt_panel._upload()
        self.yt_short_panel._upload()
        self.tiktok_panel._upload()

    def _on_auto_upload_changed(self, state):
        self.config["auto_upload"] = state == Qt.CheckState.Checked.value
