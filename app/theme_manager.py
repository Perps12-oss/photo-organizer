"""
Apply theme presets to the mutable theme token module and refresh the app shell.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import customtkinter as ctk

import theme
from assets import load_theme_background
from theme_presets import DEFAULT_PRESET_ID, THEME_PRESETS, normalize_preset_id

if TYPE_CHECKING:
    from photo_organizer_enhanced import PhotoOrganizerApp

_BTN_DERIVED = {
    "BTN_HOVER": lambda p: p.sidebar_tile_active,
    "BTN_ACTIVE": lambda p: _lighten_hex(p.border, 0.08),
    "BTN_INACTIVE_HOVER": lambda p: p.sidebar_tile_active,
    "APP_SUCCESS_HOVER": lambda _: "#16a34a",
    "APP_DANGER_HOVER": lambda _: "#dc2626",
    "APP_BTN_DISABLED_FG": lambda p: _lighten_hex(p.input_bg, 0.12),
}


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
        "BTN_NORMAL": preset.input_bg,
    }
    for name, value in mapping.items():
        setattr(theme, name, value)

    for name, fn in _BTN_DERIVED.items():
        setattr(theme, name, fn(preset))

    theme.CURRENT_PRESET_ID = pid
    return pid


class GradientBackground(ctk.CTkFrame):
    """Shell container with a full-area gradient PNG behind transparent children."""

    def __init__(self, parent, preset_id: str | None = None, **kwargs):
        super().__init__(parent, fg_color="transparent", corner_radius=0, **kwargs)
        self._preset_id = normalize_preset_id(
            preset_id or getattr(theme, "CURRENT_PRESET_ID", DEFAULT_PRESET_ID)
        )
        self._image: Optional[ctk.CTkImage] = None
        self._last_size: tuple[int, int] = (0, 0)
        self._bg_label = ctk.CTkLabel(self, text="", fg_color="transparent")
        self._bg_label.place(x=0, y=0, relwidth=1, relheight=1)
        self._bg_label.lower()
        self.set_preset(self._preset_id)
        self.bind("<Configure>", self._on_configure, add="+")
        parent.bind("<Configure>", self._on_configure, add="+")
        self.after_idle(self._on_configure)

    def _on_configure(self, event=None) -> None:
        if event is not None:
            allowed = {self, self.winfo_toplevel()}
            if event.widget not in allowed:
                return
        width = max(self.winfo_width(), 1)
        height = max(self.winfo_height(), 1)
        if width < 2 or height < 2:
            return
        if (width, height) == self._last_size:
            return
        self._last_size = (width, height)
        self._apply_image(width, height)

    def set_preset(self, preset_id: str) -> None:
        from assets import clear_theme_background_cache

        clear_theme_background_cache()
        self._preset_id = normalize_preset_id(preset_id)
        self._last_size = (0, 0)
        self._on_configure()

    def _apply_image(self, width: int, height: int) -> None:
        self._image = load_theme_background(self._preset_id, width, height)
        preset = THEME_PRESETS[self._preset_id]
        if self._image:
            self._bg_label.configure(image=self._image, text="")
            self.configure(fg_color="transparent")
        else:
            self._bg_label.configure(image=None, text="")
            self.configure(fg_color=preset.window_bg)


def refresh_shell(app: "PhotoOrganizerApp") -> None:
    """Live refresh root, sidebar, status bar, and background after theme change."""
    pid = getattr(theme, "CURRENT_PRESET_ID", DEFAULT_PRESET_ID)

    if hasattr(app, "_bg_layer") and app._bg_layer:
        app._bg_layer.set_preset(pid)

    app.configure(fg_color=theme.WINDOW_BG)

    if hasattr(app, "sidebar_frame"):
        app.sidebar_frame.refresh_theme()

    if hasattr(app, "status_bar"):
        app.status_bar.refresh_theme()

    if hasattr(app, "main_frame"):
        app.main_frame.configure(fg_color="transparent")

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
