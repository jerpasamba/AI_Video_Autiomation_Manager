import os
import winreg
from ctypes import wintypes


def _is_windows_dark_mode():
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        ) as key:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return value == 0
    except Exception:
        return True


_IS_DARK = _is_windows_dark_mode()

DARK_COLORS = {
    "bg_dark": "#11111b",
    "bg_medium": "#181825",
    "bg_card": "#1e1e2e",
    "bg_input": "#313244",
    "border": "#45475a",
    "border_light": "#585b70",
    "text_primary": "#cdd6f4",
    "text_secondary": "#a6adc8",
    "text_muted": "#6c7086",
    "text_dim": "#585b70",
    "accent_blue": "#89b4fa",
    "accent_blue_hover": "#74c7ec",
    "accent_green": "#a6e3a1",
    "accent_green_hover": "#94e2d5",
    "accent_yellow": "#f9e2af",
    "accent_yellow_hover": "#f5c2e7",
    "accent_red": "#f38ba8",
    "accent_red_hover": "#eba0ac",
    "accent_purple": "#cba6f7",
    "accent_purple_hover": "#b4befe",
    "accent_peach": "#fab387",
    "accent_peach_hover": "#f9a86c",
    "accent_teal": "#94e2d5",
    "accent_pink": "#f5c2e7",
    "accent_sky": "#89dceb",
    "facebook": "#1877f2",
    "facebook_hover": "#166fe5",
    "youtube": "#ff4444",
    "youtube_hover": "#cc3333",
    "tiktok": "#fe2c55",
    "tiktok_hover": "#e0264b",
    "scrollbar_bg": "#181825",
    "scrollbar_fg": "#45475a",
    "scrollbar_hover": "#585b70",
    "status_success": "#a6e3a1",
    "status_fail": "#f38ba8",
    "status_running": "#f9e2af",
    "status_pending": "#6c7086",
    "log_info": "#89b4fa",
    "log_warning": "#f9e2af",
    "log_error": "#f38ba8",
    "log_debug": "#6c7086",
    "log_success": "#a6e3a1",
}

LIGHT_COLORS = {
    "bg_dark": "#f5f5f5",
    "bg_medium": "#ffffff",
    "bg_card": "#ffffff",
    "bg_input": "#e8e8e8",
    "border": "#d0d0d0",
    "border_light": "#b0b0b0",
    "text_primary": "#1a1a1a",
    "text_secondary": "#555555",
    "text_muted": "#888888",
    "text_dim": "#aaaaaa",
    "accent_blue": "#1a73e8",
    "accent_blue_hover": "#1557b0",
    "accent_green": "#2e7d32",
    "accent_green_hover": "#1b5e20",
    "accent_yellow": "#f9a825",
    "accent_yellow_hover": "#f57f17",
    "accent_red": "#d32f2f",
    "accent_red_hover": "#b71c1c",
    "accent_purple": "#7b1fa2",
    "accent_purple_hover": "#4a148c",
    "accent_peach": "#e65100",
    "accent_peach_hover": "#bf360c",
    "accent_teal": "#00695c",
    "accent_pink": "#c2185b",
    "accent_sky": "#00838f",
    "facebook": "#1877f2",
    "facebook_hover": "#166fe5",
    "youtube": "#cc0000",
    "youtube_hover": "#990000",
    "tiktok": "#fe2c55",
    "tiktok_hover": "#e0264b",
    "scrollbar_bg": "#e0e0e0",
    "scrollbar_fg": "#bdbdbd",
    "scrollbar_hover": "#9e9e9e",
    "status_success": "#2e7d32",
    "status_fail": "#d32f2f",
    "status_running": "#f9a825",
    "status_pending": "#888888",
    "log_info": "#1a73e8",
    "log_warning": "#e65100",
    "log_error": "#d32f2f",
    "log_debug": "#888888",
    "log_success": "#2e7d32",
}

COLORS = DARK_COLORS if _IS_DARK else LIGHT_COLORS

# Pre-built common stylesheet fragments for performance
BTN_PRIMARY = f"background:{COLORS['accent_blue']};color:{COLORS['bg_dark']};border:none;border-radius:6px;padding:8px 16px;font-weight:bold;"
BTN_PRIMARY_HOVER = f"background:{COLORS['accent_blue_hover']};"
BTN_SUCCESS = f"background:{COLORS['accent_green']};color:{COLORS['bg_dark']};border:none;border-radius:6px;padding:8px 16px;font-weight:bold;"
BTN_SUCCESS_HOVER = f"background:{COLORS['accent_green_hover']};"
BTN_DANGER = f"background:{COLORS['accent_red']};color:{COLORS['bg_dark']};border:none;border-radius:6px;padding:8px 16px;font-weight:bold;"
BTN_DANGER_HOVER = f"background:{COLORS['accent_red_hover']};"
BTN_DIM = f"background:{COLORS['bg_input']};color:{COLORS['text_primary']};border:none;border-radius:6px;padding:8px 16px;font-weight:bold;"
BTN_DIM_HOVER = f"background:{COLORS['border']};"


def border_radius(radius):
    return f"border-radius: {radius}px;"


def btn_style(bg, hover, text=None, radius=6, padding="8px 16px"):
    if text is None:
        text = COLORS['bg_dark']
    return f"""
        QPushButton {{
            background: {bg}; color: {text};
            border: none; border-radius: {radius}px;
            padding: {padding}; font-weight: bold;
            min-height: 24px;
        }}
        QPushButton:hover {{ background: {hover}; }}
        QPushButton:disabled {{ background: {COLORS['bg_input']}; color: {COLORS['text_dim']}; }}
    """


def input_style(padding="8px 12px"):
    return f"""
        background: {COLORS['bg_input']}; color: {COLORS['text_primary']};
        border: 1px solid {COLORS['border']}; border-radius: 6px;
        padding: {padding}; font-size: 13px; min-height: 22px;
    """


def card_style():
    return f"""
        background: {COLORS['bg_card']};
        border: 1px solid {COLORS['border']};
        border-radius: 12px;
        padding: 16px;
    """


def group_style():
    return f"""
        QGroupBox {{
            font-size: 14px; font-weight: bold;
            color: {COLORS['accent_blue']};
            border: 1px solid {COLORS['border']};
            border-radius: 10px; margin-top: 14px; padding: 18px 14px 14px;
            background: {COLORS['bg_card']};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin; subcontrol-position: top left;
            padding: 2px 10px; color: {COLORS['accent_blue']};
        }}
    """


def progress_bar_style(color=None):
    if color is None:
        color = COLORS['accent_blue']
    return f"""
        QProgressBar {{
            background: {COLORS['bg_input']}; border: none;
            border-radius: 4px; height: 8px;
        }}
        QProgressBar::chunk {{
            background: {color}; border-radius: 4px;
        }}
    """


def main_stylesheet():
    """Full app stylesheet — single source of truth."""
    C = COLORS
    return f"""
        QMainWindow {{ background: {C['bg_dark']}; }}
        QWidget {{ color: {C['text_primary']}; font-size: 13px; }}
        QTabWidget::pane {{ background: {C['bg_dark']}; border: none; }}
        QTabBar::tab {{
            background: {C['bg_medium']}; color: {C['text_muted']};
            padding: 10px 20px; border: none;
            border-bottom: 2px solid transparent;
            font-weight: bold; font-size: 12px;
        }}
        QTabBar::tab:selected {{
            background: {C['bg_card']}; color: {C['text_primary']};
            border-bottom: 2px solid {C['accent_blue']};
        }}
        QTabBar::tab:hover:!selected {{
            color: {C['text_secondary']};
            border-bottom: 2px solid {C['border']};
        }}
        QScrollBar:vertical {{
            background: {C['scrollbar_bg']}; width: 10px;
            border: none; border-radius: 5px;
        }}
        QScrollBar::handle:vertical {{
            background: {C['scrollbar_fg']}; min-height: 30px;
            border-radius: 5px;
        }}
        QScrollBar::handle:vertical:hover {{ background: {C['scrollbar_hover']}; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QScrollBar:horizontal {{
            background: {C['scrollbar_bg']}; height: 10px;
            border: none; border-radius: 5px;
        }}
        QScrollBar::handle:horizontal {{
            background: {C['scrollbar_fg']}; min-width: 30px;
            border-radius: 5px;
        }}
        QScrollBar::handle:horizontal:hover {{ background: {C['scrollbar_hover']}; }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
        QStatusBar {{ background: {C['bg_medium']}; color: {C['text_secondary']}; border-top: 1px solid {C['border']}; }}
        QSplitter::handle {{ background: {C['border']}; }}
        QToolTip {{ background: {C['bg_card']}; color: {C['text_primary']}; border: 1px solid {C['border']}; padding: 4px; border-radius: 4px; }}
        QMenu {{ background: {C['bg_card']}; color: {C['text_primary']}; border: 1px solid {C['border']}; }}
        QMenu::item:selected {{ background: {C['bg_input']}; }}
    """
