"""Home dashboard view."""
import os

import customtkinter as ctk

from inbox_watcher import load_settings
from media_index import index_stats
from design_system import ElevatedCard, GhostButton, PageHeader, PrimaryButton, SecondaryButton
from theme import (
    BODY_FONT, CAPTION_FONT, CONTENT_MARGIN, FONT_MONO_SM, INPUT_BG, SECTION_GAP, TEXT_SECONDARY,
)
from i18n import t
from keyboard_bindings import shortcuts_reference_text


class HomeView(ctk.CTkFrame):
    """Start page with quick navigation."""

    def __init__(self, parent, on_duplicates, on_sort, on_inbox=None, on_gallery=None, on_settings=None):
        super().__init__(parent, fg_color="transparent")
        self.on_duplicates = on_duplicates
        self.on_sort = on_sort
        self.on_inbox = on_inbox
        self.on_gallery = on_gallery
        self.on_settings = on_settings

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        PageHeader(self, t("app.title"), t("home.welcome")).grid(
            row=0, column=0, sticky="ew", padx=CONTENT_MARGIN, pady=(CONTENT_MARGIN, SECTION_GAP),
        )

        hero = ElevatedCard(self)
        hero.grid(row=1, column=0, sticky="nsew", padx=CONTENT_MARGIN, pady=(0, CONTENT_MARGIN))
        inner = hero.body

        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.pack(pady=(SECTION_GAP, 12))

        dup_col = ctk.CTkFrame(btn_row, fg_color="transparent")
        dup_col.pack(side="left", padx=16)
        PrimaryButton(dup_col, text=t("nav.duplicates"), width=200, command=on_duplicates).pack()
        ctk.CTkLabel(dup_col, text=t("home.find_duplicates_hint"), font=CAPTION_FONT, text_color=TEXT_SECONDARY).pack(
            pady=(6, 0),
        )

        gal_col = ctk.CTkFrame(btn_row, fg_color="transparent")
        gal_col.pack(side="left", padx=16)
        SecondaryButton(
            gal_col, text=t("nav.gallery"), width=200, command=on_gallery if on_gallery else on_sort,
        ).pack()
        ctk.CTkLabel(gal_col, text=t("home.media_gallery_hint"), font=CAPTION_FONT, text_color=TEXT_SECONDARY).pack(
            pady=(6, 0),
        )

        btn_row2 = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row2.pack(pady=(4, SECTION_GAP))

        org_col = ctk.CTkFrame(btn_row2, fg_color="transparent")
        org_col.pack(side="left", padx=16)
        SecondaryButton(org_col, text=t("nav.organizer"), width=200, command=on_sort).pack()
        ctk.CTkLabel(org_col, text=t("home.file_organizer_hint"), font=CAPTION_FONT, text_color=TEXT_SECONDARY).pack(
            pady=(6, 0),
        )

        inbox_col = ctk.CTkFrame(btn_row2, fg_color="transparent")
        inbox_col.pack(side="left", padx=16)
        SecondaryButton(
            inbox_col, text=t("nav.inbox"), width=200, command=on_inbox if on_inbox else on_sort,
        ).pack()
        ctk.CTkLabel(inbox_col, text=t("home.inbox_watcher_hint"), font=CAPTION_FONT, text_color=TEXT_SECONDARY).pack(
            pady=(6, 0),
        )

        if on_settings:
            GhostButton(inner, text=t("nav.settings"), command=on_settings).pack(pady=(16, 4))

        hints = ctk.CTkFrame(inner, fg_color=INPUT_BG, corner_radius=12)
        hints.pack(fill="x", pady=10)
        ctk.CTkLabel(hints, text=t("settings.shortcuts"), font=CAPTION_FONT, text_color=TEXT_SECONDARY).pack(
            anchor="w", padx=16, pady=(12, 6),
        )
        ctk.CTkLabel(
            hints, text=shortcuts_reference_text(), font=FONT_MONO_SM, text_color=TEXT_SECONDARY, justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 14))

        stats_frame = ctk.CTkFrame(inner, fg_color=INPUT_BG, corner_radius=12)
        stats_frame.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(
            stats_frame, text="Library dashboard", font=CAPTION_FONT, text_color=TEXT_SECONDARY,
        ).pack(anchor="w", padx=16, pady=(12, 6))
        ctk.CTkLabel(
            stats_frame, text=self._library_stats(), font=FONT_MONO_SM, text_color=TEXT_SECONDARY, justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 14))

    def _library_stats(self) -> str:
        idx = index_stats()
        watcher = load_settings()
        root = (watcher.library_root or "").strip()
        root_line = root if root and os.path.isdir(root) else "(not set)"
        return (
            f"Indexed files: {idx.get('files', 0):,} across {idx.get('roots', 0)} folder(s)\n"
            f"Library root: {root_line}\n"
            f"Watcher today: {getattr(watcher, 'files_processed_today', 0)} file(s) routed"
        )
