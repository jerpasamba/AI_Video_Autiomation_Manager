COLORS = {
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
    "accent_teal": "#94e2d5",
    "accent_pink": "#f5c2e7",
    "accent_sky": "#89dceb",
    "facebook": "#1877f2",
    "facebook_hover": "#166fe5",
    "youtube": "#ff4444",
    "youtube_hover": "#cc3333",
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

def border_radius(radius):
    return f"border-radius: {radius}px;"

def btn_style(bg, hover, text="#1e1e2e", radius=6, padding="8px 16px"):
    return f"""
        QPushButton {{
            background: {bg}; color: {text};
            border: none; border-radius: {radius}px;
            padding: {padding}; font-weight: bold;
        }}
        QPushButton:hover {{ background: {hover}; }}
        QPushButton:disabled {{ background: {COLORS['bg_input']}; color: {COLORS['text_dim']}; }}
    """

def input_style():
    return f"""
        background: {COLORS['bg_input']}; color: {COLORS['text_primary']};
        border: 1px solid {COLORS['border']}; border-radius: 6px;
        padding: 10px; font-size: 13px;
    """

def card_style():
    return f"""
        background: {COLORS['bg_card']};
        border: 1px solid {COLORS['border']};
        border-radius: 12px;
        padding: 16px;
    """

def progress_bar_style(color=COLORS['accent_blue']):
    return f"""
        QProgressBar {{
            background: {COLORS['bg_input']}; border: none;
            border-radius: 4px; height: 8px;
        }}
        QProgressBar::chunk {{
            background: {color}; border-radius: 4px;
        }}
    """
