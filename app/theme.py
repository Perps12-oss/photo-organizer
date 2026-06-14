"""
Central design tokens for Photo Organizer UI.

Semantic roles:
  APP_PRIMARY     — main actions (Start Scan)
  APP_SECONDARY   — selection / highlight accents
  APP_SUCCESS     — keep / confirm strategies
  APP_DANGER      — destructive actions
  APP_SURFACE     — elevated cards and panels
  APP_BTN_OUTLINE — bordered secondary buttons
  APP_BTN_GHOST   — tertiary / text-like buttons
  APP_BTN_DISABLED — muted disabled control appearance
"""
import customtkinter as ctk

# Layout
WINDOW_DEFAULT = "1200x800"
WINDOW_MIN_W = 900
WINDOW_MIN_H = 600
SIDEBAR_WIDTH = 180

# Spacing & shape
PAD_XS = 4
PAD_SM = 8
PAD_MD = 12
PAD_LG = 16
PAD_XL = 20
CARD_RADIUS = 10
CARD_RADIUS_LG = 16
ANIM_FADE_MS = 120
ANIM_VIEW_MS = 180
APPEARANCE_MODES = ("Dark", "Light", "System")

# Surfaces
APP_BG = "#1E1E1E"
APP_SIDEBAR = "#2D2D2D"
APP_CARD = "#1a1a2e"
APP_SURFACE = APP_CARD
APP_BORDER = "#2d2d44"
APP_INPUT = "#3B3B3B"

# Text
APP_TEXT = "#F0F0F0"
APP_TEXT_MUTED = "#8899aa"

# Semantic actions (use these instead of hardcoded hex in views)
APP_ACCENT = "#00ffcc"
APP_ACCENT_HOVER = "#00ccaa"
APP_PRIMARY = APP_ACCENT
APP_PRIMARY_HOVER = APP_ACCENT_HOVER
APP_PRIMARY_TEXT = "#0a0a12"
APP_SECONDARY = "#6366f1"
APP_SECONDARY_HOVER = "#4f46e5"
APP_SUCCESS = "#198754"
APP_SUCCESS_HOVER = "#13653f"
APP_DANGER = "#dc3545"
APP_DANGER_HOVER = "#a71d2a"

# Buttons
BTN_NORMAL = "#3B3B3B"
BTN_HOVER = "#4A4A4A"
BTN_ACTIVE = "#5A5A5A"
BTN_INACTIVE = "#2a2a3e"
BTN_INACTIVE_HOVER = "#353550"
APP_BTN_OUTLINE = "transparent"
APP_BTN_GHOST = "transparent"
APP_BTN_DISABLED_FG = "#5a3a3a"
APP_BTN_DISABLED_TEXT = "#6a7a8a"

# Neon scan hero
NEON_CYAN = "#00ffcc"
NEON_MAGENTA = "#ff00ff"
NEON_BLUE = "#00ccff"
NEON_PURPLE = "#9d4edd"
NEON_BG = "#080810"
NEON_TRACK = "#141424"
NEON_TRACK_BORDER = "#2a2a4a"
NEON_ORANGE = "#ff9f43"

# Typography
FONT_TITLE = ("Segoe UI", 22, "bold")
FONT_HEADING = ("Segoe UI", 13, "bold")
FONT_BODY = ("Segoe UI", 12)
FONT_SMALL = ("Segoe UI", 11)
FONT_LABEL = ("Segoe UI", 10, "bold")
FONT_MONO = ("Consolas", 11)
FONT_MONO_SM = ("Consolas", 10)
FONT_LOGO = ("Segoe UI", 14, "bold")

# Status bar priority tiers
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


def is_dark_mode() -> bool:
    try:
        return ctk.get_appearance_mode() == "Dark"
    except Exception:
        return True


def toast_colors() -> tuple[str, str, str]:
    """bg, text, border"""
    if is_dark_mode():
        return "#2D2D2D", APP_TEXT, APP_BORDER
    return "#E8E8E8", "#1a1a1a", "#CCCCCC"


__all__ = [
    "ANIM_FADE_MS",
    "ANIM_VIEW_MS",
    "APPEARANCE_MODES",
    "APP_ACCENT",
    "APP_ACCENT_HOVER",
    "APP_BG",
    "APP_BORDER",
    "APP_BTN_DISABLED_FG",
    "APP_BTN_DISABLED_TEXT",
    "APP_BTN_GHOST",
    "APP_BTN_OUTLINE",
    "APP_CARD",
    "APP_DANGER",
    "APP_DANGER_HOVER",
    "APP_INPUT",
    "APP_PRIMARY",
    "APP_PRIMARY_HOVER",
    "APP_PRIMARY_TEXT",
    "APP_SECONDARY",
    "APP_SECONDARY_HOVER",
    "APP_SIDEBAR",
    "APP_SUCCESS",
    "APP_SUCCESS_HOVER",
    "APP_SURFACE",
    "APP_TEXT",
    "APP_TEXT_MUTED",
    "BTN_ACTIVE",
    "BTN_HOVER",
    "BTN_INACTIVE",
    "BTN_INACTIVE_HOVER",
    "BTN_NORMAL",
    "CARD_RADIUS",
    "CARD_RADIUS_LG",
    "FONT_BODY",
    "FONT_HEADING",
    "FONT_LABEL",
    "FONT_LOGO",
    "FONT_MONO",
    "FONT_MONO_SM",
    "FONT_SMALL",
    "FONT_TITLE",
    "GALLERY_SORT_OPTIONS",
    "NEON_BG",
    "NEON_BLUE",
    "NEON_CYAN",
    "NEON_MAGENTA",
    "NEON_ORANGE",
    "NEON_PURPLE",
    "NEON_TRACK",
    "NEON_TRACK_BORDER",
    "PAD_LG",
    "PAD_MD",
    "PAD_SM",
    "PAD_XL",
    "PAD_XS",
    "SIDEBAR_WIDTH",
    "STATUS_IDLE",
    "STATUS_INFO",
    "STATUS_JOB",
    "WINDOW_DEFAULT",
    "WINDOW_MIN_H",
    "WINDOW_MIN_W",
    "is_dark_mode",
    "toast_colors",
]
