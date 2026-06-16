#!/usr/bin/env python3
"""Generate abstract multigradient background PNGs for theme presets."""
from __future__ import annotations

import os
import sys

from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_DIR = os.path.join(ROOT, "app")
sys.path.insert(0, APP_DIR)

from theme_presets import THEME_PRESETS  # noqa: E402

OUT_DIR = os.path.join(ROOT, "assets", "themes")
WIDTH, HEIGHT = 1600, 900


def _blend(base: tuple[int, int, int], color: tuple[int, int, int], alpha: float) -> tuple[int, int, int]:
    a = max(0.0, min(1.0, alpha))
    return tuple(int(base[i] * (1 - a) + color[i] * a) for i in range(3))


def render_gradient(preset_id: str) -> Image.Image:
    preset = THEME_PRESETS[preset_id]
    img = Image.new("RGB", (WIDTH, HEIGHT), preset.gradient_base)
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    for cx_r, cy_r, rad_r, rgb, opacity in preset.gradient_washes:
        cx = int(WIDTH * cx_r)
        cy = int(HEIGHT * cy_r)
        radius = int(max(WIDTH, HEIGHT) * rad_r)
        alpha = int(max(0, min(255, opacity * 255)))
        left = cx - radius
        top = cy - radius
        right = cx + radius
        bottom = cy + radius
        wash = Image.new("RGBA", (right - left, bottom - top), (0, 0, 0, 0))
        wdraw = ImageDraw.Draw(wash)
        wdraw.ellipse((0, 0, right - left, bottom - top), fill=(*rgb, alpha))
        wash = wash.filter(ImageFilter.GaussianBlur(radius=max(8, radius // 6)))
        overlay.paste(wash, (left, top), wash)

    base_rgba = img.convert("RGBA")
    composed = Image.alpha_composite(base_rgba, overlay)

    # Subtle vignette
    vignette = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    vdraw = ImageDraw.Draw(vignette)
    vdraw.ellipse((-WIDTH // 4, -HEIGHT // 4, WIDTH + WIDTH // 4, HEIGHT + HEIGHT // 4), fill=(0, 0, 0, 40))
    vignette = vignette.filter(ImageFilter.GaussianBlur(radius=80))
    composed = Image.alpha_composite(composed, vignette)

    return composed.convert("RGB")


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    for preset_id in THEME_PRESETS:
        path = os.path.join(OUT_DIR, f"{preset_id}.png")
        img = render_gradient(preset_id)
        img.save(path, optimize=True)
        print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
