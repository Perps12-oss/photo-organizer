#!/usr/bin/env python3
"""Flag hardcoded hex colors outside theme/design_system modules."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"

ALLOWED = {
    APP / "theme.py",
    APP / "theme_presets.py",
    APP / "theme_manager.py",
    APP / "design_system.py",
}

# Placeholder examples in UI copy are OK
IGNORE_PATTERNS = (
    re.compile(r'placeholder_text\s*='),
)

HEX_RE = re.compile(r'#[0-9a-fA-F]{3,8}\b')


def scan_file(path: Path) -> list[tuple[int, str]]:
    if path.resolve() in {p.resolve() for p in ALLOWED}:
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    hits: list[tuple[int, str]] = []
    for i, line in enumerate(text.splitlines(), 1):
        if any(p.search(line) for p in IGNORE_PATTERNS):
            continue
        for match in HEX_RE.finditer(line):
            hits.append((i, match.group(0)))
    return hits


def main() -> int:
    offenders: list[str] = []
    for path in sorted(APP.rglob("*.py")):
        if "photo_organizer_pro" in path.name or "photo_organizer_hybrid" in path.name:
            continue
        for line_no, color in scan_file(path):
            rel = path.relative_to(ROOT)
            offenders.append(f"{rel}:{line_no}: {color}")

    if offenders:
        print("Hardcoded hex colors found outside allowed theme modules:")
        for row in offenders:
            print(f"  {row}")
        return 1

    print("OK — no stray hex colors in app/ (excluding pro/hybrid)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
