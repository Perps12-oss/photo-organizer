"""Load bundled fonts and icon assets."""
from __future__ import annotations

import os
from typing import Optional

import customtkinter as ctk
from PIL import Image

_APP_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_APP_DIR)
ASSETS_DIR = os.path.join(_ROOT, "assets")
FONTS_DIR = os.path.join(ASSETS_DIR, "fonts")
ICONS_DIR = os.path.join(ASSETS_DIR, "icons")
THEMES_DIR = os.path.join(ASSETS_DIR, "themes")

_ICON_CACHE: dict[tuple[str, int, str], ctk.CTkImage] = {}
_THEME_BG_CACHE: dict[str, ctk.CTkImage] = {}
_THEME_PIL_CACHE: dict[str, Image.Image] = {}
_FONTS_REGISTERED = False

THEME_BG_NATIVE_WIDTH = 2560
THEME_BG_NATIVE_HEIGHT = 1440


def assets_root() -> str:
    return ASSETS_DIR


def font_path(name: str) -> Optional[str]:
    path = os.path.join(FONTS_DIR, name)
    return path if os.path.isfile(path) else None


def register_fonts(root) -> str:
    """Register bundled Inter fonts with Tk; return resolved family name."""
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return "Inter"

    import tkinter.font as tkfont

    regular = font_path("Inter-Regular.ttf")
    bold = font_path("Inter-Bold.ttf")
    if regular and os.path.isfile(regular):
        try:
            tkfont.Font(root=root, name="Inter", file=regular, size=13)
            if bold and os.path.isfile(bold):
                tkfont.Font(root=root, name="Inter Bold", file=bold, size=13, weight="bold")
            _FONTS_REGISTERED = True
            return "Inter"
        except Exception:
            pass
    return "Segoe UI"


def _hex_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _tint_image(path: str, color: str, size: int) -> Image.Image:
    img = Image.open(path).convert("RGBA")
    if img.size != (size, size):
        img = img.resize((size, size), Image.Resampling.LANCZOS)
    cr, cg, cb = _hex_rgb(color)
    pixels = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            _, _, _, pa = pixels[x, y]
            if pa > 0:
                pixels[x, y] = (cr, cg, cb, pa)
    return img


def _load_theme_pil(preset_id: str) -> Optional[Image.Image]:
    if preset_id in _THEME_PIL_CACHE:
        return _THEME_PIL_CACHE[preset_id]

    path = os.path.join(THEMES_DIR, f"{preset_id}.png")
    if not os.path.isfile(path):
        return None

    pil = Image.open(path).convert("RGB")
    _THEME_PIL_CACHE[preset_id] = pil
    return pil


def resize_theme_background_pil(preset_id: str, width: int, height: int) -> Optional[Image.Image]:
    """Return gradient PNG scaled to the requested size (LANCZOS)."""
    w = max(1, int(width))
    h = max(1, int(height))
    source = _load_theme_pil(preset_id)
    if source is None:
        return None
    if source.size == (w, h):
        return source
    return source.resize((w, h), Image.Resampling.LANCZOS)


def load_theme_background(preset_id: str, width: int, height: int) -> Optional[ctk.CTkImage]:
    """Load gradient PNG for a theme preset, scaled to the requested size."""
    w = max(1, int(width))
    h = max(1, int(height))
    key = f"{preset_id}:{w}x{h}"
    if key in _THEME_BG_CACHE:
        return _THEME_BG_CACHE[key]

    scaled = resize_theme_background_pil(preset_id, w, h)
    if scaled is None:
        return None

    img = ctk.CTkImage(light_image=scaled, dark_image=scaled, size=(w, h))
    _THEME_BG_CACHE[key] = img
    return img


def clear_theme_background_cache() -> None:
    _THEME_BG_CACHE.clear()
    _THEME_PIL_CACHE.clear()


def load_icon(name: str, size: int = 20, color: Optional[str] = None) -> Optional[ctk.CTkImage]:
    key = (name, size, color or "")
    if key in _ICON_CACHE:
        return _ICON_CACHE[key]

    path = os.path.join(ICONS_DIR, f"{name}_{size}.png")
    if not os.path.isfile(path):
        for fallback in (24, 20, 32, 48, 72):
            alt = os.path.join(ICONS_DIR, f"{name}_{fallback}.png")
            if os.path.isfile(alt):
                path = alt
                break
        else:
            return None

    if color:
        pil = _tint_image(path, color, size)
        img = ctk.CTkImage(light_image=pil, dark_image=pil, size=(size, size))
    else:
        img = ctk.CTkImage(light_image=path, dark_image=path, size=(size, size))
    _ICON_CACHE[key] = img
    return img
