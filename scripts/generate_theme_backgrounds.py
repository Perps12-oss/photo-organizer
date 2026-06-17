#!/usr/bin/env python3
"""Generate abstract multigradient background PNGs for theme presets."""
from __future__ import annotations

import os
import shutil
import statistics
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_DIR = os.path.join(ROOT, "app")
sys.path.insert(0, APP_DIR)

from theme_presets import THEME_PRESETS  # noqa: E402

OUT_DIR = os.path.join(ROOT, "assets", "themes")
WIDTH, HEIGHT = 3840, 2160

# Target ~20–26% visibility; auto-boost low-contrast presets until std_dev passes.
OVERLAY_RGB = (11, 18, 32)
COLOR_VISIBLE_TARGET = 0.26
COLOR_VISIBLE_MAX = 0.58
STD_DEV_MIN = 20.0


def _hex_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _wash_opacity(opacity: float) -> float:
    return min(0.72, max(0.22, opacity * 2.4 + 0.14))


def _draw_wash(
    overlay: Image.Image,
    cx: int,
    cy: int,
    radius: int,
    rgb: tuple[int, int, int],
    opacity: float,
) -> None:
    alpha = int(max(0, min(255, opacity * 255)))
    radius = min(radius, max(WIDTH, HEIGHT) // 2)
    left = max(0, cx - radius)
    top = max(0, cy - radius)
    right = min(WIDTH, cx + radius)
    bottom = min(HEIGHT, cy + radius)
    w = right - left
    h = bottom - top
    if w <= 0 or h <= 0:
        return
    wash = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    wdraw = ImageDraw.Draw(wash)
    wdraw.ellipse((0, 0, w, h), fill=(*rgb, alpha))
    blur = min(96, max(12, radius // 8))
    wash = wash.filter(ImageFilter.GaussianBlur(radius=blur))
    overlay.paste(wash, (left, top), wash)


def _std_dev(img: Image.Image) -> float:
    px = img.load()
    w, h = img.size
    step = max(1, min(w, h) // 256)
    vals: list[int] = []
    for y in range(0, h, step):
        for x in range(0, w, step):
            r, g, b = px[x, y][:3]
            vals.extend((r, g, b))
    return statistics.pstdev(vals)


def render_gradient(preset_id: str) -> Image.Image:
    preset = THEME_PRESETS[preset_id]
    colorful = Image.new("RGB", (WIDTH, HEIGHT), preset.gradient_base)
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))

    washes = list(preset.gradient_washes)
    accent = _hex_rgb(preset.accent)
    alt = _hex_rgb(preset.accent_alt)
    washes.extend([
        (0.12, 0.18, 0.42, accent, 0.38),
        (0.88, 0.22, 0.38, alt, 0.32),
        (0.52, 0.92, 0.48, accent, 0.26),
    ])
    if preset_id == "slate_mono":
        washes = [
            (0.25, 0.35, 0.55, (0, 180, 220), 0.28),
            (0.75, 0.65, 0.45, (120, 80, 200), 0.24),
            (0.55, 0.15, 0.35, (80, 120, 180), 0.18),
            (0.12, 0.18, 0.42, (40, 160, 210), 0.40),
            (0.88, 0.22, 0.38, (100, 140, 220), 0.34),
        ]

    for cx_r, cy_r, rad_r, rgb, opacity in washes:
        cx = int(WIDTH * cx_r)
        cy = int(HEIGHT * cy_r)
        radius = int(max(WIDTH, HEIGHT) * rad_r)
        _draw_wash(overlay, cx, cy, radius, rgb, _wash_opacity(opacity))

    colorful = Image.alpha_composite(colorful.convert("RGBA"), overlay).convert("RGB")

    vignette = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    vdraw = ImageDraw.Draw(vignette)
    vdraw.ellipse(
        (-WIDTH // 5, -HEIGHT // 5, WIDTH + WIDTH // 5, HEIGHT + HEIGHT // 5),
        fill=(0, 0, 0, 20),
    )
    vignette = vignette.filter(ImageFilter.GaussianBlur(radius=100))
    colorful = Image.alpha_composite(colorful.convert("RGBA"), vignette).convert("RGB")

    navy = Image.new("RGB", (WIDTH, HEIGHT), OVERLAY_RGB)
    visible = 0.34 if preset_id == "slate_mono" else COLOR_VISIBLE_TARGET
    max_vis = 0.62 if preset_id == "slate_mono" else COLOR_VISIBLE_MAX
    composed = Image.blend(navy, colorful, visible)
    while _std_dev(composed) < STD_DEV_MIN and visible < max_vis:
        visible += 0.04
        composed = Image.blend(navy, colorful, visible)
    return composed


def _save_png(img: Image.Image, path: str) -> None:
    fd, tmp = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        img.save(tmp, format="PNG")
        if os.path.isfile(path):
            os.remove(path)
        shutil.move(tmp, path)
    except Exception:
        if os.path.isfile(tmp):
            os.remove(tmp)
        raise


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    failed: list[str] = []
    for preset_id in THEME_PRESETS:
        path = os.path.join(OUT_DIR, f"{preset_id}.png")
        img = render_gradient(preset_id)
        std = _std_dev(img)
        _save_png(img, path)
        status = "OK" if std >= STD_DEV_MIN else "LOW"
        print(f"Wrote {path}  std_dev={std:.1f}  [{status}]")
        if std < STD_DEV_MIN:
            failed.append(preset_id)

    if failed:
        print(f"\nWARNING: {len(failed)} preset(s) below std_dev {STD_DEV_MIN}: {', '.join(failed)}")
        return 1
    print(f"\nAll {len(THEME_PRESETS)} presets passed std_dev >= {STD_DEV_MIN}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
