#!/usr/bin/env python3
"""Theme token smoke test — solid surfaces from active preset (no canvas layer)."""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_DIR = os.path.join(ROOT, "app")
sys.path.insert(0, APP_DIR)

import customtkinter as ctk  # noqa: E402

from design_system import ElevatedCard, PrimaryButton  # noqa: E402
from theme import APP_SIDEBAR, APP_BORDER, STATUS_BAR_BG, WINDOW_BG  # noqa: E402
from theme_manager import apply_from_settings  # noqa: E402


def main() -> None:
    ctk.set_appearance_mode("dark")
    apply_from_settings()
    root = ctk.CTk()
    root.title("Theme shell test — preset tokens only")
    root.geometry("800x600")
    root.configure(fg_color=WINDOW_BG)

    shell = ctk.CTkFrame(root, fg_color=WINDOW_BG, corner_radius=0)
    shell.place(relwidth=1, relheight=1)
    shell.grid_columnconfigure(1, weight=1)
    shell.grid_rowconfigure(0, weight=1)

    sidebar = ctk.CTkFrame(
        shell, width=180, fg_color=APP_SIDEBAR, border_width=1, border_color=APP_BORDER, corner_radius=0,
    )
    sidebar.grid(row=0, column=0, sticky="ns")
    sidebar.grid_propagate(False)
    ctk.CTkLabel(sidebar, text="Sidebar", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=24, padx=16)

    main = ctk.CTkFrame(shell, fg_color=WINDOW_BG, corner_radius=0)
    main.grid(row=0, column=1, sticky="nsew")

    card = ElevatedCard(main)
    card.grid(row=0, column=0, padx=48, pady=48, sticky="n")
    ctk.CTkLabel(card.body, text="Theme tokens", font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w")
    PrimaryButton(card.body, text="Accent button", width=160).pack(anchor="w", pady=(12, 0))

    status = ctk.CTkFrame(
        shell, height=28, fg_color=STATUS_BAR_BG, border_width=1, border_color=APP_BORDER, corner_radius=0,
    )
    status.grid(row=1, column=0, columnspan=2, sticky="ew")

    print("PASS: themed shell opened — no black CTk transparent panels.")
    root.mainloop()


if __name__ == "__main__":
    main()
