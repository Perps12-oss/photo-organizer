"""
Apply theme presets to the mutable theme token module and refresh the app shell.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import customtkinter as ctk

import theme
from theme_presets import DEFAULT_PRESET_ID, THEME_PRESETS, normalize_preset_id

if TYPE_CHECKING:
    from photo_organizer_enhanced import PhotoOrganizerApp


def _hex_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _rgb_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02x}{g:02x}{b:02x}"


def _lighten_hex(hex_color: str, amount: float) -> str:
    r, g, b = _hex_rgb(hex_color)
    r = min(255, int(r + 255 * amount))
    g = min(255, int(g + 255 * amount))
    b = min(255, int(b + 255 * amount))
    return _rgb_hex(r, g, b)


def _hover_accent(accent: str) -> str:
    return _lighten_hex(accent, 0.12)


def apply_preset_tokens(preset_id: str, custom_accent: str = "") -> str:
    """Mutate theme module globals from preset. Returns resolved preset id."""
    pid = normalize_preset_id(preset_id)
    preset = THEME_PRESETS[pid]

    accent = custom_accent if custom_accent.startswith("#") else preset.accent
    accent_hover = _hover_accent(accent) if custom_accent.startswith("#") else preset.accent_hover

    mapping = {
        "WINDOW_BG": preset.window_bg,
        "SURFACE_BG": preset.surface_bg,
        "INPUT_BG": preset.input_bg,
        "BORDER": preset.border,
        "TEXT_PRIMARY": preset.text_primary,
        "TEXT_SECONDARY": preset.text_secondary,
        "ACCENT": accent,
        "ACCENT_ALT": preset.accent_alt,
        "ACCENT_HOVER": accent_hover,
        "SIDEBAR_TILE_ACTIVE": preset.sidebar_tile_active,
        "STATUS_BAR_BG": preset.status_bar_bg,
        "CARD_SHADOW": preset.card_shadow,
        "APP_PRIMARY_TEXT": preset.app_primary_text,
        "APP_BG": preset.window_bg,
        "APP_SIDEBAR": preset.sidebar_surface,
        "APP_CARD": preset.surface_bg,
        "APP_SURFACE": preset.surface_bg,
        "APP_BORDER": preset.border,
        "APP_INPUT": preset.input_bg,
        "APP_TEXT": preset.text_primary,
        "APP_TEXT_MUTED": preset.text_secondary,
        "APP_ACCENT": accent,
        "APP_ACCENT_HOVER": accent_hover,
        "APP_PRIMARY": accent,
        "APP_PRIMARY_HOVER": accent_hover,
        "APP_SECONDARY": preset.accent_alt,
        "APP_SECONDARY_HOVER": accent_hover,
        "APP_SUCCESS_HOVER": preset.success_hover,
        "APP_DANGER_HOVER": preset.danger_hover,
        "BTN_NORMAL": preset.input_bg,
        "BTN_HOVER": preset.sidebar_tile_active,
        "BTN_ACTIVE": preset.btn_active or _lighten_hex(preset.border, 0.08),
        "BTN_INACTIVE_HOVER": preset.sidebar_tile_active,
        "APP_BTN_DISABLED_FG": _lighten_hex(preset.input_bg, 0.12),
    }
    for name, value in mapping.items():
        setattr(theme, name, value)

    theme.CURRENT_PRESET_ID = pid
    return pid


def refresh_shell(app: "PhotoOrganizerApp") -> None:
    """Live refresh root, shell, sidebar, status bar, and views after theme change."""
    bg = theme.WINDOW_BG

    app.configure(fg_color=bg)
    if hasattr(app, "_shell"):
        app._shell.configure(fg_color=bg)
    if hasattr(app, "main_frame"):
        app.main_frame.configure(fg_color=bg)

    if hasattr(app, "sidebar_frame"):
        app.sidebar_frame.refresh_theme()

    if hasattr(app, "status_bar"):
        app.status_bar.refresh_theme()

    for attr in ("home_frame", "duplicate_frame", "gallery_frame", "sort_frame", "inbox_frame", "settings_frame"):
        view = getattr(app, attr, None)
        if view is not None and view.winfo_exists():
            try:
                view.configure(fg_color=bg)
            except Exception:
                pass

    if hasattr(app, "toast"):
        app.toast.refresh_theme()


def apply_from_settings(app: Optional["PhotoOrganizerApp"] = None) -> str:
    """Load preset + accent from app_settings and optionally refresh shell."""
    from app_settings import load_app_settings

    settings = load_app_settings()
    pid = apply_preset_tokens(settings.theme_preset, settings.custom_accent)
    if app is not None:
        refresh_shell(app)
    return pid
