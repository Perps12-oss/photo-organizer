#!/usr/bin/env python3
"""Minimal repro: composited multigradient behind CTkLabel + glass shell."""
from __future__ import annotations

import os
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_DIR = os.path.join(ROOT, "app")
sys.path.insert(0, APP_DIR)

import customtkinter as ctk  # noqa: E402
from PIL import Image  # noqa: E402

from assets import THEMES_DIR  # noqa: E402
from design_system import ElevatedCard  # noqa: E402
from theme import APP_BORDER, APP_SIDEBAR, STATUS_BAR_BG  # noqa: E402
from theme_manager import RootBackground  # noqa: E402
from theme_presets import DEFAULT_PRESET_ID  # noqa: E402


def _png_std_dev(preset_id: str) -> float:
    path = os.path.join(THEMES_DIR, f"{preset_id}.png")
    img = Image.open(path).convert("RGB")
    px = img.load()
    w, h = img.size
    step = max(1, min(w, h) // 256)
    vals: list[int] = []
    for y in range(0, h, step):
        for x in range(0, w, step):
            r, g, b = px[x, y][:3]
            vals.extend((r, g, b))
    return statistics.pstdev(vals)


def main() -> None:
    std = _png_std_dev(DEFAULT_PRESET_ID)
    print(f"Preset '{DEFAULT_PRESET_ID}' PNG std_dev={std:.1f} (need > 20)")
    if std <= 20:
        print("FAIL: regenerate backgrounds with scripts/generate_theme_backgrounds.py")
        sys.exit(1)

    ctk.set_appearance_mode("dark")
    root = ctk.CTk()
    root.title("Gradient shell test — color washes should fill window")
    root.geometry("800x600")
    root.configure(fg_color="transparent")

    bg = RootBackground(root, preset_id=DEFAULT_PRESET_ID)

    shell = ctk.CTkFrame(root, fg_color="transparent", corner_radius=0)
    shell.place(x=0, y=0, relwidth=1, relheight=1)
    shell.grid_columnconfigure(1, weight=1)
    shell.grid_rowconfigure(0, weight=1)

    sidebar = ctk.CTkFrame(
        shell, width=180, fg_color=APP_SIDEBAR, border_width=1, border_color=APP_BORDER, corner_radius=0,
    )
    sidebar.grid(row=0, column=0, sticky="ns")
    sidebar.grid_propagate(False)
    ctk.CTkLabel(sidebar, text="Sidebar", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=24, padx=16)

    main = ctk.CTkFrame(shell, fg_color="transparent", corner_radius=0)
    main.grid(row=0, column=1, sticky="nsew")

    card = ElevatedCard(main)
    card.grid(row=0, column=0, padx=48, pady=48, sticky="n")
    ctk.CTkLabel(card.body, text="Gradient test", font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w")
    ctk.CTkLabel(
        card.body,
        text="Margins and sidebar must show subtle purple/teal/cyan washes\nthrough dark glass — not flat charcoal.",
        justify="left",
    ).pack(anchor="w", pady=(8, 0))

    status = ctk.CTkFrame(
        shell, height=28, fg_color=STATUS_BAR_BG, border_width=1, border_color=APP_BORDER, corner_radius=0,
    )
    status.grid(row=1, column=0, columnspan=2, sticky="ew")
    ctk.CTkLabel(status, text="Status bar glass", font=ctk.CTkFont(size=11)).pack(side="left", padx=12)

    bg.send_to_back()
    root.after(100, bg._on_configure)
    print("PASS: window opened — verify subtle color washes visually.")
    root.mainloop()


if __name__ == "__main__":
    main()
