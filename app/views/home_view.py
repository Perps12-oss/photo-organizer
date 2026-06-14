"""Home dashboard view."""
import os

import customtkinter as ctk

from inbox_watcher import load_settings
from media_index import index_stats
from theme import APP_ACCENT, APP_ACCENT_HOVER, APP_BORDER, APP_CARD, APP_TEXT, APP_TEXT_MUTED, FONT_MONO_SM
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

        hero = ctk.CTkFrame(self, fg_color=APP_CARD, corner_radius=16, border_width=1, border_color=APP_BORDER)
        hero.pack(fill="both", expand=True, padx=8, pady=8)

        inner = ctk.CTkFrame(hero, fg_color="transparent")
        inner.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(inner, text=t("app.title"), font=ctk.CTkFont(size=36, weight="bold"),
                     text_color=APP_ACCENT).pack(pady=(0, 8))
        ctk.CTkLabel(
            inner,
            text=t("home.welcome"),
            font=ctk.CTkFont(size=14), text_color=APP_TEXT_MUTED
        ).pack(pady=(0, 32))

        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.pack(pady=(0, 8))

        dup_col = ctk.CTkFrame(btn_row, fg_color="transparent")
        dup_col.pack(side="left", padx=10)
        ctk.CTkButton(
            dup_col, text=t("nav.duplicates"), width=200, height=48,
            fg_color=APP_ACCENT, hover_color=APP_ACCENT_HOVER, text_color="#0a0a12",
            font=ctk.CTkFont(size=14, weight="bold"), command=on_duplicates
        ).pack()
        ctk.CTkLabel(dup_col, text=t("home.find_duplicates_hint"),
                     font=ctk.CTkFont(size=11), text_color=APP_TEXT_MUTED).pack(pady=(6, 0))

        gal_col = ctk.CTkFrame(btn_row, fg_color="transparent")
        gal_col.pack(side="left", padx=10)
        ctk.CTkButton(
            gal_col, text=t("nav.gallery"), width=200, height=48,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=on_gallery if on_gallery else on_sort,
        ).pack()
        ctk.CTkLabel(gal_col, text=t("home.media_gallery_hint"),
                     font=ctk.CTkFont(size=11), text_color=APP_TEXT_MUTED).pack(pady=(6, 0))

        btn_row2 = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row2.pack(pady=(8, 8))

        org_col = ctk.CTkFrame(btn_row2, fg_color="transparent")
        org_col.pack(side="left", padx=10)
        ctk.CTkButton(
            org_col, text=t("nav.organizer"), width=200, height=48,
            font=ctk.CTkFont(size=14, weight="bold"), command=on_sort
        ).pack()
        ctk.CTkLabel(org_col, text=t("home.file_organizer_hint"),
                     font=ctk.CTkFont(size=11), text_color=APP_TEXT_MUTED).pack(pady=(6, 0))

        inbox_col = ctk.CTkFrame(btn_row2, fg_color="transparent")
        inbox_col.pack(side="left", padx=10)
        ctk.CTkButton(
            inbox_col, text=t("nav.inbox"), width=200, height=48,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=on_inbox if on_inbox else on_sort,
        ).pack()
        ctk.CTkLabel(inbox_col, text=t("home.inbox_watcher_hint"),
                     font=ctk.CTkFont(size=11), text_color=APP_TEXT_MUTED).pack(pady=(6, 0))

        if on_settings:
            ctk.CTkButton(
                inner, text=f"⚙️  {t('nav.settings')}", width=160, height=36,
                fg_color="transparent", border_width=1, border_color=APP_BORDER,
                hover_color="#252540", command=on_settings,
            ).pack(pady=(16, 4))

        hints = ctk.CTkFrame(inner, fg_color="#0f0f18", corner_radius=10)
        hints.pack(padx=20, pady=10)
        ctk.CTkLabel(hints, text=t("settings.shortcuts"), font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=APP_TEXT_MUTED).pack(anchor="w", padx=16, pady=(12, 6))
        shortcut_text = shortcuts_reference_text()
        ctk.CTkLabel(hints, text=shortcut_text, font=FONT_MONO_SM, text_color="#778899",
                     justify="left").pack(anchor="w", padx=16, pady=(0, 14))

        stats = self._library_stats()
        stats_frame = ctk.CTkFrame(inner, fg_color="#0f0f18", corner_radius=10)
        stats_frame.pack(padx=20, pady=(0, 8), fill="x")
        ctk.CTkLabel(
            stats_frame, text="Library dashboard", font=ctk.CTkFont(size=11, weight="bold"),
            text_color=APP_TEXT_MUTED,
        ).pack(anchor="w", padx=16, pady=(12, 6))
        ctk.CTkLabel(
            stats_frame, text=stats, font=FONT_MONO_SM, text_color="#778899",
            justify="left",
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

