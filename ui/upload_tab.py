import os
import json
import logging

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QListWidget, QListWidgetItem,
    QFrame, QCheckBox, QGroupBox, QSplitter,
    QMessageBox, QFileDialog,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor

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
    """Interactive drag-and-drop area with platform selectors and file browser."""
    files_selected = pyqtSignal(list, list)  # (list_of_file_paths, list_of_target_platforms)
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

        # Top row: Drag prompt + Browse button
        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        self.icon_label = QLabel("📥")
        self.icon_label.setStyleSheet("font-size: 26px;")
        top_row.addWidget(self.icon_label)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        self.title_label = QLabel("Drag & Drop Video Files Here")
        self.title_label.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {COLORS['text_primary']};")
        self.sub_label = QLabel("Supports MP4, MOV, MKV, AVI, WEBM. Drop anywhere here or directly onto any platform column below.")
        self.sub_label.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.sub_label)
        top_row.addLayout(text_layout)

        top_row.addStretch()

        self.browse_btn = QPushButton("📂 Browse Video Files...")
        self.browse_btn.setStyleSheet(btn_style(COLORS['accent_blue'], COLORS['accent_blue_hover'], "white", padding="7px 16px", radius=6))
        self.browse_btn.clicked.connect(self._on_browse)
        top_row.addWidget(self.browse_btn)

        main_layout.addLayout(top_row)

        # Bottom row: Target platform checkboxes & actions
        plat_row = QHBoxLayout()
        plat_row.setSpacing(14)

        plat_lbl = QLabel("Upload To:")
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
        self.status_label.setText(f"✓ {count} video{'s' if count != 1 else ''} loaded: {names}")
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


class _PlatformPanel(QFrame):
    """Self-contained upload panel for one platform."""

    def __init__(self, platform, queue, config, load_title_fn, load_desc_fn, load_meta_fn=None, upload_tab=None, parent=None):
        super().__init__(parent)
        self.platform = platform
        self.queue = queue
        self.config = config
        self._load_title_fn = load_title_fn
        self._load_desc_fn = load_desc_fn
        self._load_meta_fn = load_meta_fn
        self.upload_tab = upload_tab
        self._selected_path = None
        self.setAcceptDrops(True)
        ps = PLATFORM_STYLES[platform]

        accent = ps["accent"]
        accent_hover = ps["accent_hover"]

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._set_drag_active(False)

        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        header = QLabel(ps["label"])
        header.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {accent};")
        layout.addWidget(header)

        self.pending_group = QGroupBox("Ready to Upload")
        self.pending_group.setStyleSheet(f"""
            QGroupBox {{
                background: {COLORS['bg_card']}; border: 1px solid {COLORS['border']};
                border-radius: 8px; padding: 12px; margin-top: 10px;
                font-size: 12px; color: {COLORS['text_muted']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin; subcontrol-position: top left;
                padding: 2px 8px;
            }}
        """)
        pending_inner = QVBoxLayout()
        pending_inner.setContentsMargins(0, 0, 0, 0)

        self.pending_list = QListWidget()
        self.pending_list.setStyleSheet(f"""
            QListWidget {{
                background: {COLORS['bg_medium']}; color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']}; border-radius: 6px;
            }}
            QListWidget::item {{ padding: 8px; font-size: 12px; }}
            QListWidget::item:selected {{ background: {accent}40; }}
        """)
        self.pending_list.itemClicked.connect(self._on_pending_selected)
        self.pending_list.itemDoubleClicked.connect(self._preview_selected)
        pending_inner.addWidget(self.pending_list)
        self.pending_group.setLayout(pending_inner)
        layout.addWidget(self.pending_group)

        self.progress_group = QGroupBox("Uploaded & Live")
        self.progress_group.setStyleSheet(f"""
            QGroupBox {{
                background: {COLORS['bg_card']}; border: 1px solid {COLORS['border']};
                border-radius: 8px; padding: 12px; margin-top: 10px;
                font-size: 12px; color: {COLORS['text_muted']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin; subcontrol-position: top left;
                padding: 2px 8px;
            }}
        """)
        progress_inner = QVBoxLayout()
        progress_inner.setContentsMargins(0, 0, 0, 0)

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

        self.upload_btn = QPushButton(f"Upload to {ps['short_label']}")
        self.upload_btn.setStyleSheet(btn_style(accent, accent_hover, "white"))
        self.upload_btn.clicked.connect(self._upload)
        layout.addWidget(self.upload_btn)

        if self.platform == "facebook":
            self.meta_biz_btn = QPushButton("Post via Business Suite 🌐")
            self.meta_biz_btn.setStyleSheet(btn_style(COLORS['bg_input'], COLORS['border'], COLORS['text_primary'], padding="6px 12px", radius=6))
            self.meta_biz_btn.setToolTip("Opens Meta Business Suite with video selected and description copied to clipboard!")
            self.meta_biz_btn.clicked.connect(self._open_business_suite)
            layout.addWidget(self.meta_biz_btn)

        layout.addStretch()
        self.setLayout(layout)

    def _set_drag_active(self, active: bool):
        ps = PLATFORM_STYLES[self.platform]
        accent = ps["accent"]
        if active:
            self.setStyleSheet(f"""
                _PlatformPanel {{
                    background: {accent}22;
                    border: 2px dashed {accent};
                    border-radius: 10px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                _PlatformPanel {{
                    background: {accent}08;
                    border: 1px solid {accent}40;
                    border-radius: 10px;
                }}
            """)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(u.toLocalFile().lower().endswith(SUPPORTED_VIDEO_EXTS) for u in urls):
                event.acceptProposedAction()
                self._set_drag_active(True)
                return
        event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self._set_drag_active(False)

    def dropEvent(self, event):
        self._set_drag_active(False)
        paths = []
        if event.mimeData().hasUrls():
            for u in event.mimeData().urls():
                fp = u.toLocalFile()
                if fp.lower().endswith(SUPPORTED_VIDEO_EXTS) and os.path.isfile(fp):
                    paths.append(fp)
        if paths:
            event.acceptProposedAction()
            if self.upload_tab:
                self.upload_tab.add_direct_videos_for_platform(paths, self.platform)
        else:
            event.ignore()

    def _open_business_suite(self):
        import subprocess, webbrowser
        from PyQt6.QtWidgets import QApplication
        cur_item = self.pending_list.currentItem()
        vpath = cur_item.data(Qt.ItemDataRole.UserRole) if cur_item else self._selected_path
        if vpath and os.path.exists(vpath):
            title = self._load_title_fn(vpath) or os.path.basename(vpath).replace(
                "_shorts.mp4", "").replace("_video.mp4", "").replace("_", " ").title()
            desc = self._load_desc_fn(vpath) or title
            clipboard_text = f"{title}\n\n{desc}\n\n#reels #viral #shorts"
            QApplication.clipboard().setText(clipboard_text)
            subprocess.run(f'explorer /select,"{vpath}"', shell=True)
        webbrowser.open("https://business.facebook.com/latest/reels_composer")

    def _on_pending_selected(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path and os.path.exists(path):
            self._selected_path = path

    def _preview_selected(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path and os.path.exists(path):
            os.startfile(path)

    def _open_upload_link(self, item):
        url = item.data(Qt.ItemDataRole.UserRole)
        if url and url.startswith("http"):
            import webbrowser
            webbrowser.open(url)

    def refresh_pending(self, videos):
        from app import upload_registry
        self.pending_list.clear()

        for itm in videos:
            if len(itm) == 3:
                label, vpath, target_plats = itm
                if target_plats and self.platform not in target_plats:
                    continue
            else:
                label, vpath = itm
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

            # Check cross-platform upload status for clear visibility
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
                tt = f"File: {os.path.basename(vpath)}\nStatus: Ready to upload to {self.platform.title()}"
                if badges:
                    tt += f"\nAlready uploaded to: {', '.join(badges)}"
                tt += "\nDouble-click to preview video locally"
                item.setToolTip(tt)

            self.pending_list.addItem(item)

        self.pending_group.setTitle(f"Ready to Upload ({self.pending_list.count()})")

    def refresh_progress(self, tasks):
        from app import upload_registry
        self.progress_list.clear()

        # 1. Show active or queued upload tasks from current session
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

        # 2. Show uploaded items directly from Video Manager (uploads.json)
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

    def _upload(self):
        videos = []
        for i in range(self.pending_list.count()):
            item = self.pending_list.item(i)
            path = item.data(Qt.ItemDataRole.UserRole)
            videos.append(path)

        if not videos:
            QMessageBox.information(self, "No Videos",
                                    f"No pending videos to upload to {self.platform}.")
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


class UploadTab(QWidget):
    def __init__(self, queue_manager, config, main_window=None, parent=None):
        super().__init__(parent)
        self.queue = queue_manager
        self.config = config
        self.main_window = main_window
        self._custom_videos = {}  # {vpath: set(target_platforms)}

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

        upload_all_btn = QPushButton("Upload All")
        upload_all_btn.setStyleSheet(btn_style(COLORS['accent_green'], COLORS['accent_green_hover']))
        upload_all_btn.clicked.connect(self._upload_all)
        header_layout.addWidget(upload_all_btn)

        layout.addLayout(header_layout)

        # Drag and Drop zone with platform selector
        self.drop_zone = VideoDropZone(self)
        self.drop_zone.files_selected.connect(self._on_drop_zone_files)
        self.drop_zone.cleared.connect(self._on_drop_zone_cleared)
        layout.addWidget(self.drop_zone)

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
        plat_set = set(platforms) if platforms else set(PLATFORM_STYLES.keys())
        self._custom_videos = {p: plat_set for p in paths}
        self._refresh_pending()

    def _on_drop_zone_cleared(self):
        self._custom_videos.clear()
        self._refresh_pending()

    def add_direct_videos_for_platform(self, paths, platform):
        """Called when videos are dragged directly onto a specific platform panel."""
        for p in paths:
            if p in self._custom_videos:
                self._custom_videos[p].add(platform)
            else:
                self._custom_videos[p] = {platform}
        self._refresh_pending()

    def _refresh_pending(self):
        try:
            self._do_refresh_pending()
        except Exception as e:
            log.warning("_refresh_pending error: %s", e)
            import traceback
            log.warning(traceback.format_exc())

    def _discover_videos(self):
        videos = []

        # 1. First add any custom dropped or selected videos
        for vpath, target_plats in self._custom_videos.items():
            if os.path.isfile(vpath):
                label = f"📁 {os.path.basename(vpath)}"
                videos.append((label, vpath, target_plats))

        # 2. Add pipeline-generated videos
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

        # Minecraft metadata
        mc_meta = os.path.join(ch_dir, os.path.splitext(os.path.basename(video_path))[0] + "_meta.json")
        if os.path.isfile(mc_meta):
            try:
                with open(mc_meta, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

        # Manhwa youtube_meta.json
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
        self.yt_panel._upload()
        self.yt_short_panel._upload()
        self.fb_panel._upload()
        self.tiktok_panel._upload()

    def _on_auto_upload_changed(self, state):
        self.config["auto_upload"] = state == Qt.CheckState.Checked.value
