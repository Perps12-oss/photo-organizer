"""Generate Lucide-style line icons as PNG for the UI (run once when adding icons)."""
from __future__ import annotations

import os
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "icons")
COLOR = "#f3f6fb"
STROKE = 2


def _canvas(size: int) -> tuple[Image.Image, ImageDraw.ImageDraw, int]:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img), size


def _save(name: str, img: Image.Image, size: int) -> None:
    os.makedirs(OUT, exist_ok=True)
    img.save(os.path.join(OUT, f"{name}_{size}.png"), "PNG")


def icon_home(size: int) -> Image.Image:
    img, d, s = _canvas(size)
    m = s * 0.2
    d.line([(m, s * 0.55), (s / 2, m), (s - m, s * 0.55)], fill=COLOR, width=STROKE)
    d.rectangle([s * 0.32, s * 0.52, s * 0.68, s - m], outline=COLOR, width=STROKE)
    return img


def icon_search(size: int) -> Image.Image:
    img, d, s = _canvas(size)
    r = s * 0.28
    cx, cy = s * 0.42, s * 0.42
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=COLOR, width=STROKE)
    d.line([(cx + r * 0.7, cy + r * 0.7), (s * 0.78, s * 0.78)], fill=COLOR, width=STROKE)
    return img


def icon_image(size: int) -> Image.Image:
    img, d, s = _canvas(size)
    m = s * 0.18
    d.rectangle([m, m, s - m, s - m], outline=COLOR, width=STROKE)
    d.ellipse([s * 0.28, s * 0.28, s * 0.42, s * 0.42], outline=COLOR, width=STROKE)
    d.line([(m, s * 0.72), (s * 0.45, s * 0.48), (s * 0.62, s * 0.58), (s - m, s * 0.35)], fill=COLOR, width=STROKE)
    return img


def icon_folder(size: int) -> Image.Image:
    img, d, s = _canvas(size)
    m = s * 0.18
    d.line([(m, s * 0.38), (s * 0.35, s * 0.38), (s * 0.42, s * 0.28), (s - m, s * 0.28)], fill=COLOR, width=STROKE)
    d.rectangle([m, s * 0.38, s - m, s - m], outline=COLOR, width=STROKE)
    return img


def icon_inbox(size: int) -> Image.Image:
    img, d, s = _canvas(size)
    m = s * 0.18
    d.rectangle([m, s * 0.28, s - m, s - m], outline=COLOR, width=STROKE)
    d.line([(m, s * 0.28), (s / 2, s * 0.48), (s - m, s * 0.28)], fill=COLOR, width=STROKE)
    return img


def icon_settings(size: int) -> Image.Image:
    img, d, s = _canvas(size)
    cx, cy = s / 2, s / 2
    r = s * 0.14
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=COLOR, width=STROKE)
    for i in range(8):
        import math
        a = i * math.pi / 4
        x1, y1 = cx + math.cos(a) * r * 1.6, cy + math.sin(a) * r * 1.6
        x2, y2 = cx + math.cos(a) * r * 2.4, cy + math.sin(a) * r * 2.4
        d.line([(x1, y1), (x2, y2)], fill=COLOR, width=STROKE)
    return img


def icon_check(size: int) -> Image.Image:
    img, d, s = _canvas(size)
    d.line([(s * 0.22, s * 0.52), (s * 0.42, s * 0.72), (s * 0.78, s * 0.32)], fill=COLOR, width=max(2, STROKE))
    return img


def icon_folder_open(size: int) -> Image.Image:
    return icon_folder(size)


ICONS = {
    "home": icon_home,
    "search": icon_search,
    "image": icon_image,
    "folder": icon_folder,
    "folder_open": icon_folder_open,
    "inbox": icon_inbox,
    "settings": icon_settings,
    "check": icon_check,
}


def main() -> None:
    for size in (20, 24, 32, 48, 72):
        for name, fn in ICONS.items():
            _save(name, fn(size), size)
    print(f"Wrote icons to {OUT}")


if __name__ == "__main__":
    main()
