"""
Design System V1 tokens for Photo Organizer UI.

Elevation, surface hierarchy, clean geometry — not glassmorphism.
"""
from __future__ import annotations

import customtkinter as ctk

from assets import register_fonts

# Layout
WINDOW_DEFAULT = "1200x800"
WINDOW_MIN_W = 900
WINDOW_MIN_H = 600
SIDEBAR_WIDTH = 220

# Spacing
CARD_PADDING = 24
SECTION_GAP = 20
CONTROL_GAP = 12
CONTENT_MARGIN = 32
PAD_XS = 4
PAD_SM = 8
PAD_MD = 12
PAD_LG = 16
PAD_XL = 20

# Shape
CARD_RADIUS = 18
INPUT_RADIUS = 12
BTN_RADIUS = 14
CARD_RADIUS_LG = CARD_RADIUS
ANIM_FADE_MS = 120
ANIM_VIEW_MS = 180
APPEARANCE_MODES = ("Dark", "Light", "System")

# Active multigradient preset (mutated by theme_manager.apply_preset_tokens)
CURRENT_PRESET_ID = "default"

# V1 color stack
WINDOW_BG = "#1a1d24"
SURFACE_BG = "#222731"
INPUT_BG = "#1e222b"
BORDER = "#2f3645"
TEXT_PRIMARY = "#f3f6fb"
TEXT_SECONDARY = "#8a95a5"
ACCENT = "#00f2fe"
ACCENT_ALT = "#4facfe"
ACCENT_HOVER = "#14d9ff"
SUCCESS = "#22c55e"
WARNING = "#f59e0b"
ERROR = "#ef4444"
SIDEBAR_TILE_ACTIVE = "#293140"
STATUS_BAR_BG = "#16242c"
CARD_SHADOW = "#1d222b"

# Legacy aliases (migrate views gradually)
APP_BG = WINDOW_BG
APP_SIDEBAR = WINDOW_BG
APP_CARD = SURFACE_BG
APP_SURFACE = SURFACE_BG
APP_BORDER = BORDER
APP_INPUT = INPUT_BG
APP_TEXT = TEXT_PRIMARY
APP_TEXT_MUTED = TEXT_SECONDARY
APP_ACCENT = ACCENT
APP_ACCENT_HOVER = ACCENT_HOVER
APP_PRIMARY = ACCENT
APP_PRIMARY_HOVER = ACCENT_HOVER
APP_PRIMARY_TEXT = "#0a1218"
APP_SECONDARY = ACCENT_ALT
APP_SECONDARY_HOVER = ACCENT_HOVER
APP_SUCCESS = SUCCESS
APP_SUCCESS_HOVER = "#16a34a"
APP_DANGER = ERROR
APP_DANGER_HOVER = "#dc2626"

BTN_NORMAL = INPUT_BG
BTN_HOVER = SIDEBAR_TILE_ACTIVE
BTN_ACTIVE = "#30384a"
BTN_INACTIVE = "transparent"
BTN_INACTIVE_HOVER = SIDEBAR_TILE_ACTIVE
APP_BTN_OUTLINE = "transparent"
APP_BTN_GHOST = "transparent"
APP_BTN_DISABLED_FG = "#3a3f4a"
APP_BTN_DISABLED_TEXT = TEXT_SECONDARY

# Typography — populated by init_fonts()
FONT_FAMILY: tuple[str, ...] = ("Inter", "Segoe UI")
_font_family_name = "Segoe UI"
TITLE_FONT: ctk.CTkFont | None = None
SECTION_FONT: ctk.CTkFont | None = None
BODY_FONT: ctk.CTkFont | None = None
CAPTION_FONT: ctk.CTkFont | None = None
FONT_TITLE = ("Segoe UI", 22, "bold")
FONT_HEADING = ("Segoe UI", 13, "bold")
FONT_BODY = ("Segoe UI", 12)
FONT_SMALL = ("Segoe UI", 11)
FONT_LABEL = ("Segoe UI", 10, "bold")
FONT_MONO = ("Consolas", 11)
FONT_MONO_SM = ("Consolas", 10)
FONT_LOGO = ("Segoe UI", 14, "bold")

STATUS_IDLE = 0
STATUS_INFO = 1
STATUS_JOB = 2

GALLERY_SORT_OPTIONS = (
    "Date (newest)",
    "Date (oldest)",
    "Name (A-Z)",
    "Name (Z-A)",
    "Rating (high)",
    "Rating (low)",
)


def init_fonts(root) -> str:
    """Register bundled Inter and build CTkFont instances. Call once at startup."""
    global _font_family_name, TITLE_FONT, SECTION_FONT, BODY_FONT, CAPTION_FONT
    global FONT_TITLE, FONT_HEADING, FONT_BODY, FONT_SMALL, FONT_LABEL, FONT_LOGO

    _font_family_name = register_fonts(root)
    FONT_FAMILY = (_font_family_name, "Segoe UI")

    TITLE_FONT = ctk.CTkFont(family=_font_family_name, size=28, weight="bold")
    SECTION_FONT = ctk.CTkFont(family=_font_family_name, size=16, weight="bold")
    BODY_FONT = ctk.CTkFont(family=_font_family_name, size=13)
    CAPTION_FONT = ctk.CTkFont(family=_font_family_name, size=11)

    FONT_TITLE = (_font_family_name, 28, "bold")
    FONT_HEADING = (_font_family_name, 16, "bold")
    FONT_BODY = (_font_family_name, 13)
    FONT_SMALL = (_font_family_name, 11)
    FONT_LABEL = (_font_family_name, 11, "bold")
    FONT_LOGO = (_font_family_name, 14, "bold")
    return _font_family_name


def get_font_family() -> str:
    return _font_family_name


def is_dark_mode() -> bool:
    return True


def toast_colors() -> tuple[str, str, str]:
    return SURFACE_BG, TEXT_PRIMARY, BORDER
