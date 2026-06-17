#!/usr/bin/env python3
"""Non-GUI verification for theme background pipeline."""
from __future__ import annotations

import statistics
import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_DIR = os.path.join(ROOT, "app")
sys.path.insert(0, APP_DIR)

from assets import resize_theme_background_pil, THEMES_DIR  # noqa: E402
from theme_presets import THEME_PRESETS, DEFAULT_PRESET_ID  # noqa: E402


def _std_sample(pil) -> float:
    px = pil.load()
    w, h = pil.size
    step = max(1, min(w, h) // 128)
    vals = [c for y in range(0, h, step) for x in range(0, w, step) for c in px[x, y][:3]]
    return statistics.pstdev(vals)


def main() -> int:
    from photo_organizer_enhanced import PhotoOrganizerApp  # noqa: F401
    from theme_manager import RootBackground  # noqa: F401

    print("import OK")
    failed = []
    for pid in THEME_PRESETS:
        path = os.path.join(THEMES_DIR, f"{pid}.png")
        if not os.path.isfile(path):
            print(f"MISSING {path}")
            failed.append(pid)
            continue
        pil = resize_theme_background_pil(pid, 800, 600)
        std = _std_sample(pil)
        ok = std > 20
        print(f"  {pid}: std_dev={std:.1f} {'OK' if ok else 'FAIL'}")
        if not ok:
            failed.append(pid)

    if failed:
        print(f"FAIL: {', '.join(failed)}")
        return 1
    print(f"PASS: all presets std_dev > 20 (default={DEFAULT_PRESET_ID})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
