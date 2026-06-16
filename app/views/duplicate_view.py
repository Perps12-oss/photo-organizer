"""Duplicate finder view and scan hero overlay."""
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw, ImageFont
import os
import hashlib
import threading
import datetime
import logging
import shutil
import math
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional
import cv2
import numpy as np

try:
    import xxhash
    HAS_XXHASH = True
except ImportError:
    HAS_XXHASH = False
    logging.warning("xxhash not available. Install with: pip install xxhash")

from duplicate_utils import cluster_phash, filter_duplicate_groups, is_similar_group
from app_settings import SCAN_DEPTH_OPTIONS, load_app_settings, push_recent_scan_folder, save_app_settings, scan_depth_to_days
from fast_hash import full_hash, hash_many_parallel, quick_hash
from file_utils import normalize_filepath, should_skip_dir, unreadable_reason
from theme import (
    APP_BORDER, APP_BTN_DISABLED_FG, APP_BTN_DISABLED_TEXT, APP_BTN_GHOST, APP_BTN_OUTLINE,
    APP_DANGER, APP_DANGER_HOVER, APP_INPUT, APP_PRIMARY, APP_PRIMARY_HOVER, APP_PRIMARY_TEXT,
    APP_SECONDARY, APP_SUCCESS, APP_SUCCESS_HOVER, APP_SURFACE, APP_TEXT, APP_TEXT_MUTED,
    ACCENT, ACCENT_HOVER, BODY_FONT, BTN_ACTIVE, BTN_HOVER, CAPTION_FONT, CARD_RADIUS, CONTENT_MARGIN, CONTROL_GAP,
    FONT_BODY, FONT_HEADING, FONT_LABEL, FONT_MONO, FONT_MONO_SM, FONT_SMALL, FONT_TITLE,
    SECTION_FONT, SECTION_GAP, TEXT_SECONDARY, WARNING,
)
from design_system import (
    DangerButton, ElevatedCard, GhostButton, LabeledEntry, ModernSlider, PageHeader,
    PrimaryButton, ResultsCard, ScanProgressCard, SecondaryButton, SectionLabel,
    StyledCheckBox, StyledOptionMenu,
)
from ui_components import DUPLICATE_SHORTCUTS, EmptyState, VirtualGroupList
from media_viewer import SideBySideCompareDialog
from services.file_operation_service import FileOperationService
from i18n import t
from views.helpers import (
    HAS_IMAGEHASH,
    calculate_fast_score,
    calculate_image_score,
    calculate_perceptual_hash,
    count_duplicate_stats,
    format_elapsed,
    format_eta,
    get_score_color,
    is_image_file,
    truncate_middle,
)

SUPPORTED_EXTENSIONS = (
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.mov', '.mp4',
    '.heic', '.heif', '.avi', '.mkv', '.mp3', '.pdf', '.doc', '.docx',
)
HASH_WORKERS = min(12, max(6, (os.cpu_count() or 4) + 2))
SCORE_WORKERS = 4
BROWSE_THUMB_SIZE = 80
BROWSE_THUMB_MAX = 24
BROWSE_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp", ".heic", ".heif"}



class DuplicateView(ctk.CTkFrame):
    def __init__(self, parent, app=None, file_ops: FileOperationService | None = None, shortcut_manager=None):
        super().__init__(parent, fg_color="transparent")
        self._app = app
        self._file_ops = file_ops
        self._shortcut_manager = shortcut_manager

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.thumb_size = (280, 280)
        self.scan_cancelled = False
        self._scan_skipped_count = 0
        self._scan_running = False
        self._silent_scan = False
        self._on_scan_complete = None
        self._scan_max_age_days: Optional[int] = None
        self._live_dup_groups = 0
        self._live_dup_files = 0
        self._live_candidates = 0
        self._last_scan_total = 0
        self._ui_mode = "pre"

        self.current_duplicates = {}
        self.current_group_files = []
        self.files_to_delete = set()
        self.group_buttons = []
        self.current_selected_group = None
        self.image_scores = {}
        self.perceptual_hashes = {}
        self.gallery_grid = None
        self._group_list = []
        self.focused_image_index = 0
        self._key_bindings = []

        _app = load_app_settings()

        self.header = PageHeader(
            self, t("nav.duplicates"), t("duplicates.subtitle"),
        )
        self.header.grid(row=0, column=0, sticky="ew", padx=CONTENT_MARGIN, pady=(CONTENT_MARGIN, SECTION_GAP))

        self.pre_scan_panel = ctk.CTkFrame(self, fg_color="transparent")
        self.pre_scan_panel.grid(row=1, column=0, sticky="nsew", padx=CONTENT_MARGIN, pady=(0, CONTENT_MARGIN))
        self.pre_scan_panel.grid_columnconfigure(0, weight=0, minsize=420)
        self.pre_scan_panel.grid_columnconfigure(1, weight=1)
        self.pre_scan_panel.grid_rowconfigure(0, weight=1)
        self.pre_scan_panel.grid_rowconfigure(1, weight=0)

        self.settings_card = ElevatedCard(self.pre_scan_panel)
        self.settings_card.grid(row=0, column=0, sticky="nsew", padx=(0, SECTION_GAP))
        settings = self.settings_card.body

        SectionLabel(settings, "Select Folder", number=1).pack(anchor="w", pady=(0, CONTROL_GAP))
        self.folder_path = ctk.StringVar(value="")
        path_row = ctk.CTkFrame(settings, fg_color="transparent")
        path_row.pack(fill="x", pady=(0, CONTROL_GAP))
        path_row.grid_columnconfigure(0, weight=1)
        self.entry = LabeledEntry(
            path_row, textvariable=self.folder_path,
            placeholder_text="Select folder to scan...",
        )
        self.entry.grid(row=0, column=0, sticky="ew", padx=(0, CONTROL_GAP))
        self.browse_btn = SecondaryButton(path_row, text="Browse", command=self.browse_folder, width=90)
        self.browse_btn.grid(row=0, column=1)

        self.recent_row = ctk.CTkFrame(settings, fg_color="transparent")
        self.recent_row.pack(fill="x", pady=(0, SECTION_GAP))

        SectionLabel(settings, "Scan Scope", number=2).pack(anchor="w", pady=(0, CONTROL_GAP))
        scope_row = ctk.CTkFrame(settings, fg_color="transparent")
        scope_row.pack(fill="x", pady=(0, SECTION_GAP))
        ctk.CTkLabel(scope_row, text="Scan depth", font=BODY_FONT, text_color=APP_TEXT).pack(
            side="left", padx=(0, CONTROL_GAP),
        )
        self.scan_depth_var = ctk.StringVar(value=_app.scan_depth_label)
        StyledOptionMenu(
            scope_row, variable=self.scan_depth_var, values=list(SCAN_DEPTH_OPTIONS), width=160,
        ).pack(side="left")

        SectionLabel(settings, "Precision", number=3).pack(anchor="w", pady=(0, CONTROL_GAP))
        prec_frame = ctk.CTkFrame(settings, fg_color="transparent")
        prec_frame.pack(fill="x", pady=(0, SECTION_GAP))
        if HAS_IMAGEHASH:
            row1 = ctk.CTkFrame(prec_frame, fg_color="transparent")
            row1.pack(fill="x", pady=(0, CONTROL_GAP))
            ctk.CTkLabel(row1, text="Image similarity", font=BODY_FONT, text_color=APP_TEXT).pack(side="left")
            self.phash_tolerance_var = ctk.IntVar(value=_app.phash_tolerance)
            self._phash_tol_label = ctk.CTkLabel(row1, text=str(_app.phash_tolerance), width=28, font=BODY_FONT)
            self._phash_tol_label.pack(side="right")
            ModernSlider(
                prec_frame, from_=0, to=16, number_of_steps=16,
                variable=self.phash_tolerance_var,
                command=lambda v: self._phash_tol_label.configure(text=str(int(float(v)))),
            ).pack(fill="x", pady=(0, CONTROL_GAP))
            ctk.CTkLabel(
                prec_frame, text="0 = exact only · 16 = loose match",
                font=CAPTION_FONT, text_color=TEXT_SECONDARY,
            ).pack(anchor="w", pady=(0, CONTROL_GAP))
        else:
            self.phash_tolerance_var = ctk.IntVar(value=5)

        self.video_tolerance_var = ctk.IntVar(value=_app.video_duplicate_tolerance)
        row2 = ctk.CTkFrame(prec_frame, fg_color="transparent")
        row2.pack(fill="x", pady=(0, CONTROL_GAP))
        ctk.CTkLabel(row2, text="Video similarity", font=BODY_FONT, text_color=APP_TEXT).pack(side="left")
        self._video_tol_label = ctk.CTkLabel(
            row2, text=str(_app.video_duplicate_tolerance), width=28, font=BODY_FONT,
        )
        self._video_tol_label.pack(side="right")
        ModernSlider(
            prec_frame, from_=0, to=16, number_of_steps=16,
            variable=self.video_tolerance_var,
            command=lambda v: self._video_tol_label.configure(text=str(int(float(v)))),
        ).pack(fill="x")

        SectionLabel(settings, "Advanced", number=4).pack(anchor="w", pady=(SECTION_GAP, CONTROL_GAP))
        self.scan_videos_var = ctk.BooleanVar(value=True)
        self.video_check = StyledCheckBox(
            settings, text="Similar videos (install ffmpeg)", variable=self.scan_videos_var,
        )
        self.video_check.pack(anchor="w", pady=(0, SECTION_GAP))

        self.scan_btn = PrimaryButton(
            settings, text="Start Scan", icon="search", command=self.start_scan_thread,
        )
        self.scan_btn.pack(fill="x", pady=(SECTION_GAP, 0))

        self.results_column = ctk.CTkFrame(self.pre_scan_panel, fg_color="transparent")
        self.results_column.grid(row=0, column=1, sticky="nsew")
        self.results_column.grid_rowconfigure(0, weight=1)
        self.results_column.grid_columnconfigure(0, weight=1)

        self.results_card = ResultsCard(self.results_column)
        self.results_card.grid(row=0, column=0, sticky="nsew")

        self.scan_progress = ScanProgressCard(self.results_column)
        self.scan_progress.grid(row=0, column=0, sticky="nsew")
        self.scan_progress.grid_remove()

        self.scan_hero = self.scan_progress

        self.pre_scan_footer = ElevatedCard(self.pre_scan_panel)
        self.pre_scan_footer.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(SECTION_GAP, 0))
        footer_body = self.pre_scan_footer.body
        ctk.CTkLabel(
            footer_body,
            text="Tip: pick a folder, tune similarity sliders, then Start Scan. "
                 "Deleted files go to quarantine (undo with Ctrl+Z).",
            font=CAPTION_FONT,
            text_color=TEXT_SECONDARY,
            anchor="w",
        ).pack(side="left", fill="x", expand=True)
        footer_actions = ctk.CTkFrame(footer_body, fg_color="transparent")
        footer_actions.pack(side="right")
        self.open_scan_folder_btn = SecondaryButton(
            footer_actions, text="Open Scanned Folder", width=150,
            command=self._open_scan_folder,
        )
        self.open_scan_folder_btn.pack(side="left", padx=(0, CONTROL_GAP))
        self.open_quarantine_btn = GhostButton(
            footer_actions, text="Open Quarantine", width=130,
            command=self._open_quarantine_folder,
        )
        self.open_quarantine_btn.pack(side="left")

        self.post_scan_panel = ctk.CTkFrame(self, fg_color="transparent")
        self.post_scan_panel.grid_columnconfigure(0, weight=0, minsize=280)
        self.post_scan_panel.grid_columnconfigure(1, weight=1)
        self.post_scan_panel.grid_rowconfigure(2, weight=1)

        self.summary_card = ElevatedCard(self.post_scan_panel)
        self.summary_card.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, SECTION_GAP))
        sum_inner = self.summary_card.body
        self.summary_label = ctk.CTkLabel(
            sum_inner, text="", font=SECTION_FONT, text_color=APP_TEXT, anchor="w",
        )
        self.summary_label.pack(side="left", fill="x", expand=True)
        SecondaryButton(
            sum_inner, text="Adjust scan", width=100, command=self._show_pre_scan_mode,
        ).pack(side="right", padx=(8, 0))

        self.results_header = ElevatedCard(self.post_scan_panel)
        self.results_header.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, SECTION_GAP))
        filter_bar = self.results_header.body
        self.dup_group_type_var = ctk.StringVar(value="all")
        self.dup_sort_var = ctk.StringVar(value="count_desc")
        self.dup_path_filter_var = ctk.StringVar(value="")
        self.dup_min_size_var = ctk.StringVar(value="0")
        self.dup_max_size_var = ctk.StringVar(value="0")
        ctk.CTkLabel(filter_bar, text="Filter", font=CAPTION_FONT, text_color=TEXT_SECONDARY).pack(
            side="left", padx=(0, CONTROL_GAP),
        )
        StyledOptionMenu(
            filter_bar, variable=self.dup_group_type_var,
            values=["all", "exact", "similar", "video"], width=90,
            command=lambda _: self._rebuild_group_sidebar(),
        ).pack(side="left", padx=4)
        StyledOptionMenu(
            filter_bar, variable=self.dup_sort_var,
            values=["count_desc", "count_asc", "newest", "oldest", "size_desc"], width=110,
            command=lambda _: self._rebuild_group_sidebar(),
        ).pack(side="left", padx=4)
        LabeledEntry(
            filter_bar, textvariable=self.dup_path_filter_var,
            placeholder_text="Path contains…", width=120,
        ).pack(side="left", padx=4)
        LabeledEntry(
            filter_bar, textvariable=self.dup_min_size_var, placeholder_text="Min KB", width=70,
        ).pack(side="left", padx=2)
        LabeledEntry(
            filter_bar, textvariable=self.dup_max_size_var, placeholder_text="Max KB", width=70,
        ).pack(side="left", padx=2)
        SecondaryButton(filter_bar, text="Apply", width=60, command=self._rebuild_group_sidebar).pack(
            side="left", padx=4,
        )
        self.dup_filter_count_label = ctk.CTkLabel(
            filter_bar, text="", font=CAPTION_FONT, text_color=TEXT_SECONDARY,
        )
        self.dup_filter_count_label.pack(side="left", padx=8)
        self.delete_btn = DangerButton(
            filter_bar, text="Delete 0 selected", command=self.confirm_delete, width=170,
        )
        self.delete_btn.pack(side="right", padx=(8, 0))

        self.list_card = ElevatedCard(self.post_scan_panel)
        self.list_card.grid(row=2, column=0, sticky="nsew", padx=(0, SECTION_GAP))
        self.list_card.grid_rowconfigure(1, weight=1)
        list_body = self.list_card.body
        list_body.grid_rowconfigure(1, weight=1)
        list_body.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            list_body, text="Duplicate groups", font=SECTION_FONT, text_color=APP_TEXT,
        ).grid(row=0, column=0, sticky="w", pady=(0, CONTROL_GAP))
        self.virtual_group_list = VirtualGroupList(
            list_body, on_select=self._on_virtual_group_select,
        )
        self.virtual_group_list.grid(row=1, column=0, sticky="nsew")
        self.list_container = self.list_card

        self.right_panel = ctk.CTkFrame(self.post_scan_panel, fg_color="transparent")
        self.right_panel.grid(row=2, column=1, sticky="nsew")
        self.right_panel.grid_columnconfigure(0, weight=1)
        self.right_panel.grid_rowconfigure(1, weight=1)

        self.gallery_controls = ElevatedCard(self.right_panel)
        self.gallery_controls.grid(row=0, column=0, sticky="ew", pady=(0, CONTROL_GAP))
        gal_bar = self.gallery_controls.body
        self.btn_smart_best = PrimaryButton(
            gal_bar, text="Smart Best", command=lambda: self.smart_select("smart_best"), width=110,
        )
        self.btn_smart_best.pack(side="left", padx=(0, 4))
        self.btn_sel_newest = SecondaryButton(
            gal_bar, text="Keep Newest", command=lambda: self.smart_select("keep_newest"), width=110,
        )
        self.btn_sel_newest.pack(side="left", padx=4)
        self.btn_sel_largest = SecondaryButton(
            gal_bar, text="Keep Largest", command=lambda: self.smart_select("keep_largest"), width=110,
        )
        self.btn_sel_largest.pack(side="left", padx=4)
        self.btn_sel_oldest = GhostButton(
            gal_bar, text="Keep Oldest", command=lambda: self.smart_select("keep_oldest"), width=100,
        )
        self.btn_sel_oldest.pack(side="left", padx=4)
        self.btn_sel_smallest = GhostButton(
            gal_bar, text="Keep Smallest", command=lambda: self.smart_select("keep_smallest"), width=110,
        )
        self.btn_sel_smallest.pack(side="left", padx=4)
        self.more_select_var = ctk.StringVar(value="More…")
        self.more_select_menu = StyledOptionMenu(
            gal_bar, variable=self.more_select_var,
            values=["More…", "Select all", "Clear all"],
            width=100, command=self._on_more_autoselect,
        )
        self.more_select_menu.pack(side="left", padx=4)
        self.compare_btn = SecondaryButton(
            gal_bar, text="Compare Selected", width=130, command=self.compare_selected,
        )
        self.compare_btn.configure(state="disabled")
        self.compare_btn.pack(side="left", padx=4)
        ctk.CTkLabel(
            gal_bar, text="↑↓ groups  ←→ images  Space  Enter  ?",
            font=FONT_MONO_SM, text_color=TEXT_SECONDARY,
        ).pack(side="right", padx=(8, 0))
        self.btn_sel_all = ctk.CTkButton(self.gallery_controls, text="", width=1, height=1)
        self.btn_clear = ctk.CTkButton(self.gallery_controls, text="", width=1, height=1)
        self._action_buttons = [
            self.btn_smart_best, self.btn_sel_newest, self.btn_sel_oldest,
            self.btn_sel_largest, self.btn_sel_smallest, self.more_select_menu,
            self.compare_btn,
        ]

        self.recommendation_panel = ctk.CTkFrame(
            self.right_panel, fg_color=APP_INPUT, corner_radius=8,
            border_width=1, border_color=APP_BORDER,
        )
        self.recommendation_panel.grid(row=2, column=0, sticky="ew", pady=(6, 0), padx=2)
        self.recommendation_label = ctk.CTkLabel(
            self.recommendation_panel,
            text="Select a duplicate group to see keep recommendations.",
            font=FONT_SMALL, text_color=APP_TEXT_MUTED, wraplength=700, justify="left",
        )
        self.recommendation_label.pack(anchor="w", padx=12, pady=8)
        self.recommendation_panel.grid_remove()

        self.gallery_outer = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        self.gallery_outer.grid(row=1, column=0, sticky="nsew")
        self.gallery_outer.grid_rowconfigure(1, weight=1)
        self.gallery_outer.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            self.gallery_outer, text="Select images to delete",
            font=FONT_HEADING,
        ).grid(row=0, column=0, sticky="w", padx=5, pady=(0, 5))
        self.gallery_frame = ctk.CTkFrame(self.gallery_outer, fg_color="transparent")
        self.gallery_frame.grid(row=1, column=0, sticky="nsew")
        self.gallery_frame.grid_columnconfigure(0, weight=1)
        self.gallery_frame.grid_rowconfigure(0, weight=1)

        self.action_bar = ElevatedCard(self.post_scan_panel)
        self.action_bar.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(SECTION_GAP, 0))
        self.status_label = ctk.CTkLabel(
            self.action_bar.body, text="Select a folder and click Start Scan",
            text_color=TEXT_SECONDARY, font=BODY_FONT,
        )
        self.status_label.pack(side="left")

        self.post_scan_panel.grid_remove()
        self._refresh_recent_chips()
        self._check_video_ffmpeg()
        self.update_delete_btn()
        self._show_pre_scan_mode()

    def _show_pre_scan_mode(self, *, keep_result: bool = False):
        self._ui_mode = "pre"
        self.unbind_review_keys()
        self.post_scan_panel.grid_remove()
        self.pre_scan_panel.grid(row=1, column=0, sticky="nsew")
        self.grid_rowconfigure(1, weight=1)
        if not keep_result:
            self._hide_pre_scan_result()

    def _hide_pre_scan_result(self):
        self.results_card.grid()
        self.results_card.show_idle()

    def _show_pre_scan_result(self, title: str, subtitle: str, total_count: int = 0, elapsed: str = ""):
        stats = []
        if total_count:
            stats.append(("Files Scanned", f"{total_count:,}"))
        if elapsed:
            stats.append(("Time Elapsed", elapsed))
        stats.append(("Duplicates Found", "0"))
        self.results_card.grid()
        self.results_card.show_success(
            title,
            subtitle,
            stats=stats,
            action_text="Scan Again",
            action=self.start_scan_thread,
        )

    def _show_scan_progress(self):
        self.results_card.grid_remove()
        self.scan_progress.show(on_cancel=self.cancel_scan)
        app = self._get_app()
        if app:
            app.set_sidebar_scanning(True, "Scanning")

    def _hide_scan_progress(self):
        self.scan_progress.hide()
        self.results_card.grid()
        app = self._get_app()
        if app:
            app.set_sidebar_scanning(False, "Ready")

    def _show_post_scan_mode(self, summary_text: str = ""):
        self._ui_mode = "post"
        self.pre_scan_panel.grid_remove()
        self.post_scan_panel.grid(row=1, column=0, sticky="nsew", padx=CONTENT_MARGIN, pady=(0, CONTENT_MARGIN))
        self.grid_rowconfigure(1, weight=1)
        if summary_text:
            self.summary_label.configure(text=summary_text)

    def _format_scan_summary(self, dup_count: int, total_count: int) -> str:
        dup_files = sum(len(paths) for paths in self.current_duplicates.values())
        total_bytes = 0
        for paths in self.current_duplicates.values():
            for p in paths:
                try:
                    total_bytes += os.path.getsize(p)
                except OSError:
                    pass
        parts = [
            f"Scanned {total_count:,} files",
            f"{dup_count} groups",
            f"{dup_files:,} duplicate files",
        ]
        if total_bytes >= 1024 * 1024:
            parts.append(f"{total_bytes / (1024 ** 3):.2f} GB")
        return " · ".join(parts)

    def _group_kind(self, h: str) -> str:
        if h.startswith("video_"):
            return "video"
        if h.startswith("pHash_"):
            return "similar"
        return "exact"

    def _on_virtual_group_select(self, index: int):
        item = self.virtual_group_list.get_group_at(index)
        if item:
            h, paths = item
            self.load_group(h, paths, index)

    def _refresh_recent_chips(self):
        for widget in self.recent_row.winfo_children():
            widget.destroy()
        folders = load_app_settings().recent_scan_folders[:3]
        if not folders:
            return
        ctk.CTkLabel(
            self.recent_row, text="Recent:", font=FONT_SMALL, text_color=APP_TEXT_MUTED,
        ).pack(side="left", padx=(0, 6))
        for path in folders:
            label = os.path.basename(path) or path
            if len(label) > 28:
                label = label[:25] + "…"
            GhostButton(
                self.recent_row, text=label, command=lambda p=path: self._apply_recent_folder(p),
            ).pack(side="left", padx=4)

    def _apply_recent_folder(self, path: str):
        if os.path.isdir(path):
            self.folder_path.set(path)

    def _check_video_ffmpeg(self):
        from video_thumbs import ffmpeg_available
        if ffmpeg_available():
            return
        self.scan_videos_var.set(False)
        self.video_check.configure(state="disabled", text="Similar videos (install ffmpeg)")
        app = self._get_app()
        if app and not getattr(self, "_ffmpeg_toast_shown", False):
            self._ffmpeg_toast_shown = True
            app.toast.show("ffmpeg not found — video duplicate detection disabled")

    def _on_more_autoselect(self, choice: str):
        self.more_select_var.set("More…")
        if choice == "Select all":
            self.smart_select("all")
        elif choice == "Clear all":
            self.smart_select("clear")

    def _show_gallery_empty(self, icon="🔍", title="", subtitle="", action_text=None, action=None):
        for widget in self.gallery_frame.winfo_children():
            widget.destroy()
        self.gallery_grid = None
        self.gallery_empty = EmptyState(
            self.gallery_frame, icon=icon, title=title, subtitle=subtitle,
            action_text=action_text, action=action,
        )
        self.gallery_empty.pack(expand=True, pady=80)

    def rebind_shortcuts(self):
        self.bind_review_keys()

    def bind_review_keys(self):
        self.unbind_review_keys()
        root = self.winfo_toplevel()
        sm = self._shortcut_manager
        if sm:
            bindings = {
                "dup_group_prev": (lambda e: self._nav_group(-1), "<Up>"),
                "dup_group_next": (lambda e: self._nav_group(1), "<Down>"),
                "dup_image_prev": (lambda e: self._nav_image(-1), "<Left>"),
                "dup_image_next": (lambda e: self._nav_image(1), "<Right>"),
                "dup_toggle_mark": (lambda e: self._toggle_focused_image(), "<space>"),
                "dup_smart_best": (lambda e: self.smart_select("smart_best"), "<Return>"),
                "dup_delete": (lambda e: self.confirm_delete(), "<Delete>"),
                "dup_help": (lambda e: self._show_keyboard_help(), "<question>"),
                "dup_home": (lambda e: self._go_home(), "<Escape>"),
                "dup_compare": (lambda e: self.compare_selected(), "<Control-d>"),
            }
            for action, (handler, default) in bindings.items():
                sm.bind(root, action, default, handler)
            return
        keys = {
            "<Up>": lambda e: self._nav_group(-1),
            "<Down>": lambda e: self._nav_group(1),
            "<Left>": lambda e: self._nav_image(-1),
            "<Right>": lambda e: self._nav_image(1),
            "<space>": lambda e: self._toggle_focused_image(),
            "<Return>": lambda e: self.smart_select("smart_best"),
            "<Delete>": lambda e: self.confirm_delete(),
            "<question>": lambda e: self._show_keyboard_help(),
            "<Escape>": lambda e: self._go_home(),
        }
        for seq, handler in keys.items():
            root.bind(seq, handler, add="+")
            self._key_bindings.append((root, seq, handler))

    def unbind_review_keys(self):
        root = self.winfo_toplevel()
        sm = self._shortcut_manager
        if sm:
            sm.unbind_actions(root, [
                "dup_group_prev", "dup_group_next", "dup_image_prev", "dup_image_next",
                "dup_toggle_mark", "dup_smart_best", "dup_delete", "dup_help", "dup_home",
                "dup_compare",
            ])
        for root, seq, handler in self._key_bindings:
            try:
                root.unbind(seq, handler)
            except Exception:
                pass
        self._key_bindings.clear()

    def _scan_active(self):
        try:
            return self.scan_hero.winfo_ismapped()
        except Exception:
            return False

    def _go_home(self):
        app = self._get_app()
        if app and not self._scan_active():
            app.show_home_frame()

    def _show_keyboard_help(self):
        app = self._get_app()
        if app:
            app._show_shortcuts_help(DUPLICATE_SHORTCUTS, "Duplicate review shortcuts")

    def _nav_group(self, delta):
        if self._scan_active() or not self._group_list:
            return "break"
        idx = self.current_selected_group if self.current_selected_group is not None else 0
        idx = (idx + delta) % len(self._group_list)
        h, paths = self._group_list[idx]
        self.load_group(h, paths, idx)
        return "break"

    def _nav_image(self, delta):
        if self._scan_active() or not self.gallery_grid:
            return "break"
        cards = list(self._iter_gallery_cards())
        if not cards:
            return "break"
        self.focused_image_index = (self.focused_image_index + delta) % len(cards)
        self._update_image_focus()
        return "break"

    def _toggle_focused_image(self):
        if self._scan_active() or not self.gallery_grid:
            return "break"
        cards = list(self._iter_gallery_cards())
        if not cards or self.focused_image_index >= len(cards):
            return "break"
        card = cards[self.focused_image_index]
        var = card.meta_data["var"]
        var.set(not var.get())
        self.handle_checkbox(card.meta_data["path"], var)
        return "break"

    def _update_image_focus(self):
        cards = list(self._iter_gallery_cards())
        for i, card in enumerate(cards):
            if card.meta_data["path"] in self.files_to_delete:
                border, width = APP_DANGER, 2
            elif i == self.focused_image_index:
                border, width = APP_SECONDARY, 3
            else:
                border, width = "gray", 2
            card.configure(border_color=border, border_width=width)
            if card.meta_data.get("img_container"):
                ic = card.meta_data["img_container"]
                ic.configure(
                    border_color=APP_DANGER if card.meta_data["path"] in self.files_to_delete else
                    (APP_SECONDARY if i == self.focused_image_index else "gray"),
                )

    def _open_folder_in_explorer(self, folder: str) -> bool:
        if not folder or not os.path.isdir(folder):
            messagebox.showinfo("Open folder", "Folder not found or not selected yet.")
            return False
        if os.name == "nt":
            os.startfile(folder)  # type: ignore[attr-defined]
        else:
            import subprocess
            subprocess.Popen(["xdg-open", folder])
        return True

    def _open_scan_folder(self):
        self._open_folder_in_explorer(self.folder_path.get().strip())

    def _open_quarantine_folder(self):
        from operation_journal import QUARANTINE_DIR
        quarantine = str(QUARANTINE_DIR)
        os.makedirs(quarantine, exist_ok=True)
        self._open_folder_in_explorer(quarantine)

    def browse_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.folder_path.set(path)
            push_recent_scan_folder(path)
            self._refresh_recent_chips()
            self.status_label.configure(text="Folder selected — ready to scan")

    def _get_app(self):
        if self._app is not None:
            return self._app
        widget = self.winfo_toplevel()
        if (
            hasattr(widget, "op_journal")
            and hasattr(widget, "toast")
            and hasattr(widget, "show_home_frame")
        ):
            return widget
        return None

    def _get_file_ops(self) -> FileOperationService | None:
        if self._file_ops is not None:
            return self._file_ops
        app = self._get_app()
        if app and hasattr(app, "file_ops"):
            return app.file_ops
        if app and hasattr(app, "op_journal"):
            return FileOperationService(app.op_journal)
        return None

    def _report_global_status(self, message: str, current_file: str = ""):
        app = self._get_app()
        if not app:
            return
        if current_file:
            name = truncate_middle(os.path.basename(current_file), 40)
            app.status.safe_job_status(f"Scanning: {name} — {message}")
        else:
            app.status.safe_job_status(message)

    def _set_scan_lock(self, locked: bool):
        state = "disabled" if locked else "normal"
        self.scan_btn.configure(state=state)
        self.browse_btn.configure(state=state)
        self.entry.configure(state=state)
        self.delete_btn.configure(state="disabled" if locked else "normal")
        if not locked:
            self.update_delete_btn()
        for btn in self._action_buttons:
            btn.configure(state=state)
        for btn in (self.open_scan_folder_btn, self.open_quarantine_btn):
            btn.configure(state=state)
        app = self._get_app()
        if app:
            app.set_navigation_enabled(not locked)

    def cancel_scan(self):
        if self.scan_cancelled:
            return
        self.scan_cancelled = True
        hero = self.scan_hero
        hero.set_progress(
            hero.target_progress,
            status="Cancelling scan — stopping after current step…",
        )
        self.status_label.configure(text="Cancelling scan…", text_color=WARNING)
        self._report_global_status("Cancelling scan…")

    def is_scan_running(self) -> bool:
        return self._scan_running

    def start_scan_thread(
        self,
        max_age_days: Optional[int] = None,
        silent: bool = False,
        on_complete=None,
    ):
        if self._scan_running:
            if not silent:
                messagebox.showinfo("Scan in progress", "A duplicate scan is already running.")
            return

        path = self.folder_path.get()
        if not path or not os.path.isdir(path):
            if not silent:
                messagebox.showerror("Error", "Please select a valid folder.")
            return

        if max_age_days is None:
            max_age_days = scan_depth_to_days(self.scan_depth_var.get())

        settings = load_app_settings()
        settings.scan_depth_label = self.scan_depth_var.get()
        if HAS_IMAGEHASH:
            settings.phash_tolerance = int(self.phash_tolerance_var.get())
        settings.video_duplicate_tolerance = int(self.video_tolerance_var.get())
        save_app_settings(settings)
        push_recent_scan_folder(path)
        self._refresh_recent_chips()

        self.scan_cancelled = False
        self._scan_skipped_count = 0
        self._scan_running = True
        self._silent_scan = silent
        self._on_scan_complete = on_complete
        self._scan_max_age_days = max_age_days
        self._live_dup_groups = 0
        self._live_dup_files = 0
        self._live_candidates = 0
        self._last_scan_total = 0
        self.group_buttons = []
        self.current_duplicates = {}
        self.image_scores = {}
        self.perceptual_hashes = {}
        self.virtual_group_list.set_groups([], {}, self._group_kind)
        self._hide_pre_scan_result()

        for widget in self.gallery_frame.winfo_children():
            widget.destroy()
        self.gallery_grid = None

        depth_hint = f" (last {max_age_days} days)" if max_age_days else ""
        if silent:
            self._report_global_status(f"Background scan{depth_hint}…")
        else:
            self.status_label.configure(text="Scanning in progress...", text_color=WARNING)
            self._report_global_status(f"Phase 1/5: Collecting files{depth_hint}...")
            self._set_scan_lock(True)
            self._show_scan_progress()
            self.scan_hero.set_progress(0, 0, 0, f"Phase 1/5: Collecting files{depth_hint}...")

        thread = threading.Thread(
            target=self.scan_duplicates,
            args=(path, max_age_days, silent),
            daemon=True,
        )
        thread.start()

    def scan_duplicates(self, path, max_age_days: Optional[int] = None, silent: bool = False):
        hashes: dict[str, list[str]] = {}
        perceptual_hashes: dict[str, list[str]] = {}

        depth_hint = f" (last {max_age_days} days)" if max_age_days else ""
        collect_label = f"Phase 1/5: Collecting files{depth_hint}..."
        self.after(0, lambda: self._scan_progress(0, 0, 0, collect_label, "", silent))

        cutoff_time = time.time() - max_age_days * 86400 if max_age_days else None
        all_files: list[tuple[str, int]] = []
        skipped_count = 0
        age_skipped = 0
        for root, dirs, files in os.walk(path):
            if self.scan_cancelled:
                self.after(0, self._cancel_scan_ui, len(all_files))
                return
            dirs[:] = [d for d in dirs if not should_skip_dir(d)]
            for file in files:
                if self.scan_cancelled:
                    self.after(0, self._cancel_scan_ui, len(all_files))
                    return
                if not file.lower().endswith(SUPPORTED_EXTENSIONS):
                    continue
                full_path = normalize_filepath(os.path.join(root, file))
                skip_reason = unreadable_reason(full_path)
                if skip_reason:
                    skipped_count += 1
                    if skipped_count <= 3:
                        logging.debug("Skipping unreadable file %s: %s", full_path, skip_reason)
                    continue
                if cutoff_time is not None:
                    try:
                        if os.path.getmtime(full_path) < cutoff_time:
                            age_skipped += 1
                            continue
                    except OSError:
                        skipped_count += 1
                        continue
                try:
                    all_files.append((full_path, os.path.getsize(full_path)))
                    if len(all_files) % 250 == 0 and not silent:
                        n = len(all_files)
                        self.after(
                            0,
                            lambda c=n: self.update_progress(
                                min(0.07, 0.01 + c / 200_000),
                                c, 0,
                                f"Phase 1/5: Collecting files ({c:,} found){depth_hint}...",
                                full_path,
                            ),
                        )
                except OSError as e:
                    skipped_count += 1
                    logging.debug("Could not stat %s: %s", full_path, e)

        self._scan_skipped_count = skipped_count
        if skipped_count:
            logging.info(
                "Skipped %d file(s) that could not be read (common with Yandex.Disk / "
                "OneDrive cloud-only files — make them available offline to include them).",
                skipped_count,
            )
        if age_skipped and max_age_days:
            logging.info("Skipped %d file(s) older than %d days.", age_skipped, max_age_days)

        total_files = len(all_files)
        if not silent:
            self.after(
                0,
                lambda: self.update_progress(
                    0.08, total_files, total_files,
                    f"Phase 1/5: Found {total_files:,} files{depth_hint} — grouping…",
                    "",
                ),
            )
        if self.scan_cancelled:
            self.after(0, self._cancel_scan_ui, 0)
            return

        size_groups: dict[int, list[str]] = defaultdict(list)
        for full_path, size in all_files:
            size_groups[size].append(full_path)

        paths_to_quick_hash: list[str] = []
        for paths in size_groups.values():
            if len(paths) > 1:
                paths_to_quick_hash.extend(paths)
        skipped_by_size = total_files - len(paths_to_quick_hash)
        self._live_candidates = len(paths_to_quick_hash)
        self.after(
            0, lambda: self.update_progress(
                0.08, total_files, total_files,
                f"Phase 2/5: Grouping by size ({total_files:,} files)...", "",
                duplicate_groups=0, duplicate_files=0, candidates=self._live_candidates,
            ),
        )

        def _cancelled() -> bool:
            return self.scan_cancelled

        def _report_hash_phase(done: int, total: int, filepath: str, label: str, base: float, span: float):
            progress = base + span * (done / max(total, 1))
            msg = f"{label} ({done:,}/{total:,})..."
            dg, df, cand = self._live_dup_groups, self._live_dup_files, self._live_candidates
            self.after(0, lambda p=progress, d=done, t=total, m=msg, fp=filepath, dg=dg, df=df, c=cand: (
                self.update_progress(p, d, t, m, fp, duplicate_groups=dg, duplicate_files=df, candidates=c)
            ))

        # Phase 3: quick hash (first 1 MB) — parallel, very fast on large libraries
        quick_total = len(paths_to_quick_hash)
        self.after(
            0, self.update_progress, 0.12, 0, quick_total,
            f"Phase 3/5: Quick-hash {quick_total:,} size matches "
            f"({skipped_by_size:,} unique sizes skipped)...",
            paths_to_quick_hash[0] if paths_to_quick_hash else "",
        )

        quick_hashes = hash_many_parallel(
            paths_to_quick_hash,
            quick_hash,
            max_workers=HASH_WORKERS,
            on_progress=lambda d, t, fp: _report_hash_phase(
                d, t, fp, "Phase 3/5: Quick-hash", 0.12, 0.28,
            ),
            cancel_check=_cancelled,
        )

        if self.scan_cancelled:
            self.after(0, self._cancel_scan_ui, len(quick_hashes))
            return

        # Only full-hash files whose quick hash collides within the same size bucket
        paths_to_full_hash: list[str] = []
        for _size, paths in size_groups.items():
            if len(paths) < 2:
                continue
            bucket_quick: dict[str, list[str]] = defaultdict(list)
            for fp in paths:
                qh = quick_hashes.get(fp)
                if qh:
                    bucket_quick[qh].append(fp)
            for group in bucket_quick.values():
                if len(group) > 1:
                    paths_to_full_hash.extend(group)
        paths_to_full_hash = list(dict.fromkeys(paths_to_full_hash))
        self._live_candidates = len(paths_to_full_hash)

        full_total = len(paths_to_full_hash)
        self.after(
            0, lambda: self.update_progress(
                0.42, 0, full_total,
                f"Phase 4/5: Full-hash {full_total:,} quick-hash collisions "
                f"({quick_total - full_total:,} cleared)...",
                paths_to_full_hash[0] if paths_to_full_hash else "",
                duplicate_groups=self._live_dup_groups,
                duplicate_files=self._live_dup_files,
                candidates=self._live_candidates,
            ),
        )

        full_hashes: dict[str, str] = {}
        hash_done = 0
        if full_total:
            pool = ThreadPoolExecutor(max_workers=HASH_WORKERS)
            cancelled = False
            try:
                futures = {pool.submit(full_hash, fp): fp for fp in paths_to_full_hash}
                for fut in as_completed(futures):
                    if self.scan_cancelled:
                        cancelled = True
                        for pending in futures:
                            pending.cancel()
                        break
                    fp = futures[fut]
                    try:
                        digest = fut.result()
                    except Exception:
                        digest = None
                    if digest:
                        full_hashes[fp] = digest
                        hashes.setdefault(digest, []).append(fp)
                        self._live_dup_groups, self._live_dup_files = count_duplicate_stats(hashes)
                    hash_done += 1
                    if hash_done % 4 == 0 or hash_done == full_total:
                        progress = 0.42 + 0.48 * (hash_done / full_total)
                        msg = f"Phase 4/5: Full-hash ({hash_done:,}/{full_total:,})..."
                        dg, df, cand = self._live_dup_groups, self._live_dup_files, self._live_candidates
                        self.after(0, lambda p=progress, d=hash_done, t=full_total, m=msg, f=fp, dg=dg, df=df, c=cand: (
                            self.update_progress(
                                p, d, t, m, f, duplicate_groups=dg, duplicate_files=df, candidates=c,
                            )
                        ))
            finally:
                if cancelled:
                    pool.shutdown(wait=False, cancel_futures=True)
                else:
                    pool.shutdown(wait=True)

        if self.scan_cancelled:
            self.after(0, self._cancel_scan_ui, hash_done)
            return

        self.after(
            0, self.update_progress, 0.92, full_total, full_total,
            "Phase 5/5: Finding similar images (duplicate groups only)...", "",
        )

        phash_targets: set[str] = set()
        for paths in hashes.values():
            if len(paths) > 1:
                phash_targets.update(p for p in paths if is_image_file(p))
        for _size, paths in size_groups.items():
            if len(paths) < 2:
                continue
            bucket_quick: dict[str, list[str]] = defaultdict(list)
            for fp in paths:
                qh = quick_hashes.get(fp)
                if qh:
                    bucket_quick[qh].append(fp)
            for group in bucket_quick.values():
                if len(group) < 2:
                    continue
                full_set = {full_hashes.get(fp) for fp in group}
                full_set.discard(None)
                if len(full_set) > 1:
                    phash_targets.update(p for p in group if is_image_file(p))

        # Perceptual hash on duplicate-group images only — not the whole library
        paths_hashes: list[tuple[str, str]] = []
        if HAS_IMAGEHASH and phash_targets:
            image_dup_paths = list(phash_targets)
            phash_done = 0
            phash_total = len(image_dup_paths)

            def _phash_one(path: str) -> Optional[tuple[str, str]]:
                h = calculate_perceptual_hash(path)
                return (path, h) if h else None

            pool = ThreadPoolExecutor(max_workers=SCORE_WORKERS)
            phash_cancelled = False
            try:
                futures = [pool.submit(_phash_one, fp) for fp in image_dup_paths]
                for fut in as_completed(futures):
                    if self.scan_cancelled:
                        phash_cancelled = True
                        for pending in futures:
                            pending.cancel()
                        break
                    result = fut.result()
                    if result:
                        paths_hashes.append(result)
                    phash_done += 1
                    if phash_done % 5 == 0 or phash_done == phash_total:
                        progress = 0.92 + 0.06 * (phash_done / max(phash_total, 1))
                        dg, df = self._live_dup_groups, self._live_dup_files
                        fp = image_dup_paths[min(phash_done - 1, phash_total - 1)] if phash_total else ""
                        self.after(
                            0, lambda p=progress, d=phash_done, t=phash_total, f=fp, dg=dg, df=df: (
                                self.update_progress(
                                    p, d, t,
                                    f"Phase 5/5: Similar-image check ({d:,}/{t:,})...",
                                    f, duplicate_groups=dg, duplicate_files=df,
                                    candidates=self._live_candidates,
                                )
                            ),
                        )
            finally:
                if phash_cancelled:
                    pool.shutdown(wait=False, cancel_futures=True)
                else:
                    pool.shutdown(wait=True)

        if self.scan_cancelled:
            self.after(0, self._cancel_scan_ui, len(full_hashes))
            return

        self.current_duplicates = {k: v for k, v in hashes.items() if len(v) > 1}

        if HAS_IMAGEHASH and paths_hashes:
            tol = int(self.phash_tolerance_var.get()) if hasattr(self, "phash_tolerance_var") else load_app_settings().phash_tolerance
            for key, paths in cluster_phash(paths_hashes, tol).items():
                if key not in self.current_duplicates:
                    self.current_duplicates[key] = paths
            app = load_app_settings()
            if app.phash_tolerance != tol:
                app.phash_tolerance = tol
                save_app_settings(app)

        if getattr(self, "scan_videos_var", None) and self.scan_videos_var.get():
            from video_dupes import is_video_file, video_fingerprint, cluster_video_fingerprints
            video_items: list[tuple[str, str]] = []
            seen_videos: set[str] = set()
            for paths in size_groups.values():
                if len(paths) < 2:
                    continue
                for fp in paths:
                    if fp in seen_videos or not is_video_file(fp):
                        continue
                    seen_videos.add(fp)
                    vf = video_fingerprint(fp)
                    if vf:
                        video_items.append((fp, vf))
            vid_tol = int(self.video_tolerance_var.get()) if hasattr(self, "video_tolerance_var") else (
                load_app_settings().video_duplicate_tolerance
            )
            for key, paths in cluster_video_fingerprints(video_items, vid_tol).items():
                if key not in self.current_duplicates:
                    self.current_duplicates[key] = paths
            app = load_app_settings()
            if app.video_duplicate_tolerance != vid_tol:
                app.video_duplicate_tolerance = vid_tol
                save_app_settings(app)

        from duplicate_utils import cluster_document_simhash, document_text_fingerprint
        from audio_fingerprint import audio_fingerprint, is_audio_file

        doc_items: list[tuple[str, str]] = []
        for paths in size_groups.values():
            if len(paths) < 2:
                continue
            for fp in paths:
                ext = os.path.splitext(fp)[1].lower()
                if ext not in (".txt", ".pdf"):
                    continue
                fp_doc = document_text_fingerprint(fp)
                if fp_doc:
                    doc_items.append((fp, fp_doc))
        for key, paths in cluster_document_simhash(doc_items, tolerance=3).items():
            if key not in self.current_duplicates:
                self.current_duplicates[key] = paths

        audio_items: list[tuple[str, str]] = []
        for paths in size_groups.values():
            if len(paths) < 2:
                continue
            for fp in paths:
                if not is_audio_file(fp):
                    continue
                af = audio_fingerprint(fp)
                if af:
                    audio_items.append((fp, af))
        audio_buckets: dict[str, list[str]] = defaultdict(list)
        for path, af in audio_items:
            audio_buckets.setdefault(af, []).append(path)
        for af, paths in audio_buckets.items():
            if len(paths) > 1:
                key = f"audio_{af}"
                if key not in self.current_duplicates:
                    self.current_duplicates[key] = paths

        self._live_dup_groups = len(self.current_duplicates)
        self._live_dup_files = sum(len(v) for v in self.current_duplicates.values())
        self.after(
            0, lambda: self.update_progress(
                0.98, total_files, total_files, "Finalizing duplicate groups...", "",
                duplicate_groups=self._live_dup_groups,
                duplicate_files=self._live_dup_files,
                candidates=self._live_candidates,
            ),
        )

        self.after(0, self.update_list_ui, len(self.current_duplicates), total_files, skipped_count)

    def _parse_size_kb_filter(self, var: ctk.StringVar) -> int:
        try:
            return max(0, int((var.get() or "0").strip()))
        except (TypeError, ValueError):
            return 0

    def _ensure_group_scores(self, paths: list[str], async_update: bool = True):
        """Compute quality scores on demand when a duplicate group is opened."""
        missing = [p for p in paths if p not in self.image_scores]
        if not missing:
            return

        def _compute_scores():
            with ThreadPoolExecutor(max_workers=SCORE_WORKERS) as pool:
                futures = {pool.submit(calculate_image_score, fp, True): fp for fp in missing}
                for fut in as_completed(futures):
                    fp = futures[fut]
                    try:
                        score = fut.result()
                    except Exception:
                        score = calculate_fast_score(fp)
                    self.image_scores[fp] = score
                    if async_update:
                        self.after(0, self._update_card_score, fp, score)

        if async_update:
            threading.Thread(target=_compute_scores, daemon=True).start()
        else:
            _compute_scores()

    def _update_card_score(self, path: str, score: float):
        """Refresh score badge on a gallery card after async scoring."""
        score_color = get_score_color(score)
        for widget in self._iter_gallery_cards():
            meta = getattr(widget, "meta_data", None)
            if not meta or meta.get("path") != path:
                continue
            meta["score"] = score
            score_frame = meta.get("score_frame")
            score_label = meta.get("score_label")
            if score_frame is not None:
                score_frame.configure(fg_color=score_color)
            if score_label is not None:
                score_label.configure(text=f"⭐ Quality Score: {score:.1f}")
            break
        if hasattr(self, "virtual_group_list") and self._group_list:
            self.virtual_group_list.set_groups(self._group_list, self.image_scores, self._group_kind)

    def _scan_progress(
        self, progress, scanned=0, total=0, status=None, current_file="", silent: bool = False,
    ):
        if silent or self._silent_scan:
            if status:
                self._report_global_status(status, current_file)
            return
        self.update_progress(progress, scanned, total, status, current_file)

    def update_progress(
        self, progress, scanned=None, total=None, status=None, current_file="",
        duplicate_groups=None, duplicate_files=None, candidates=None,
    ):
        self.scan_hero.set_progress(
            progress, scanned, total, status, current_file,
            duplicate_groups=duplicate_groups, duplicate_files=duplicate_files, candidates=candidates,
        )
        if status:
            hero = self.scan_hero
            eff_total = total if total is not None else hero.total
            eff_scanned = scanned if scanned is not None else hero.scanned
            if eff_total > 0:
                pct = int((eff_scanned / eff_total) * 100) if eff_total else 0
                self._report_global_status(f"{status} ({pct}%)", current_file)
            else:
                self._report_global_status(status, current_file)

    def update_list_ui(self, dup_count, total_count, skipped_count: int = 0):
        if self._silent_scan:
            self.after(0, lambda: self._finish_scan_ui(dup_count, total_count, skipped_count))
            return

        def after_flash():
            self.after(700, lambda: self._finish_scan_ui(dup_count, total_count, skipped_count))

        self.scan_hero.flash_complete(after_flash, duplicate_groups=dup_count)

    def _cancel_scan_ui(self, scanned_count):
        silent = self._silent_scan
        self._scan_running = False
        self._silent_scan = False
        cb = self._on_scan_complete
        self._on_scan_complete = None
        if not silent:
            self.scan_hero.hide()
            self._hide_scan_progress()
            self._set_scan_lock(False)
            app = self._get_app()
            if app:
                app.status.safe_end_job(
                    f"Scan cancelled after {scanned_count:,} files.",
                    clear_after_ms=4000,
                )
            self.status_label.configure(
                text=f"Scan cancelled after {scanned_count:,} files.",
                text_color=WARNING,
            )
            self._show_pre_scan_mode()
        elif cb:
            cb(0, scanned_count, 0)

    def _finish_scan_ui(self, dup_count, total_count, skipped_count: int = 0):
        silent = self._silent_scan
        self._scan_running = False
        self._silent_scan = False
        if not silent:
            self.scan_hero.hide()
            self._hide_scan_progress()
            self._set_scan_lock(False)
        skip_note = ""
        if skipped_count:
            skip_note = (
                f" ({skipped_count:,} cloud/offline file(s) skipped — "
                "download them in Yandex.Disk to scan)"
            )
        app = self._get_app()
        if app and not silent:
            if dup_count > 0:
                msg = f"Scan complete — {dup_count} duplicate group(s) in {total_count:,} files{skip_note}"
                app.status.safe_end_job(msg, clear_after_ms=6000)
                app.toast.show(f"Found {dup_count} duplicate group(s)")
            else:
                app.status.safe_end_job(
                    f"No duplicates in {total_count:,} files{skip_note}",
                    clear_after_ms=5000,
                )
                app.toast.show("No duplicates found")
            if skipped_count:
                app.toast.show(f"Skipped {skipped_count:,} unreadable cloud file(s)")

        cb = self._on_scan_complete
        self._on_scan_complete = None
        if cb:
            cb(dup_count, total_count, skipped_count)

        self._last_scan_total = total_count

        if dup_count > 0:
            summary = self._format_scan_summary(dup_count, total_count)
            self._show_post_scan_mode(summary)
            self.bind_review_keys()
        else:
            self._show_pre_scan_mode(keep_result=True)
            self.unbind_review_keys()
            self._show_pre_scan_result(
                "No duplicates found",
                f"Great! Your media collection is clean.{skip_note}",
                total_count=total_count,
            )

        self._rebuild_group_sidebar(
            dup_count=dup_count, total_count=total_count, skip_note=skip_note, auto_select=dup_count > 0,
        )
        return

    def _rebuild_group_sidebar(self, dup_count=None, total_count=None, skip_note="", auto_select=False):
        filtered = filter_duplicate_groups(
            self.current_duplicates,
            group_type=self.dup_group_type_var.get(),
            path_contains=self.dup_path_filter_var.get(),
            min_size_kb=self._parse_size_kb_filter(self.dup_min_size_var),
            max_size_kb=self._parse_size_kb_filter(self.dup_max_size_var),
            sort_by=self.dup_sort_var.get(),
        )
        self._group_list = filtered
        self.virtual_group_list.set_groups(filtered, self.image_scores, self._group_kind)
        if hasattr(self, "dup_filter_count_label"):
            self.dup_filter_count_label.configure(
                text=f"{len(filtered)} / {len(self.current_duplicates)} groups",
            )

        if dup_count is None:
            dup_count = len(self.current_duplicates)
        if total_count is None:
            total_count = getattr(self, "_last_scan_total", 0)

        if dup_count > 0:
            self.status_label.configure(
                text=f"Found {dup_count} duplicate groups in {total_count:,} files{skip_note} — select a group to review.",
                text_color=APP_TEXT,
            )
        else:
            self.status_label.configure(
                text=f"No duplicates found in {total_count:,} files.{skip_note}",
                text_color=APP_TEXT_MUTED,
            )

        if auto_select and filtered:
            h, paths = filtered[0]
            self.virtual_group_list.select_index(0, fire=False)
            self.load_group(h, paths, 0)

    def _compute_thumb_size(self, num_images, cols):
        """Size thumbnails to fit the available gallery area."""
        self.update_idletasks()
        avail_w = max(400, self.gallery_frame.winfo_width())
        avail_h = max(300, self.gallery_frame.winfo_height())
        rows = math.ceil(num_images / cols)
        meta_h = 130
        pad = 30
        max_by_h = (avail_h - rows * pad) // max(rows, 1) - meta_h
        max_by_w = (avail_w - cols * pad) // max(cols, 1)
        side = min(max_by_h, max_by_w, 400)
        side = max(160, int(side))
        return (side, side)

    def _iter_gallery_cards(self):
        if not self.gallery_grid:
            return
        for widget in self.gallery_grid.winfo_children():
            if hasattr(widget, "meta_data"):
                yield widget

    def load_group(self, file_hash, paths, button_index):
        self._ensure_group_scores(paths, async_update=True)
        self.virtual_group_list.select_index(button_index, fire=False)
        self.current_selected_group = button_index

        self.current_group_hash = file_hash
        self.current_group_files = paths
        self.files_to_delete = set()

        # Clear gallery
        for widget in self.gallery_frame.winfo_children():
            widget.destroy()
        self.gallery_grid = None

        num_images = len(paths)
        cols = min(3, num_images)
        rows = math.ceil(num_images / cols)
        self.thumb_size = self._compute_thumb_size(num_images, cols)

        # Scroll only when many rows; otherwise expand cards into available space
        if rows > 3:
            container = ctk.CTkScrollableFrame(self.gallery_frame, fg_color="transparent")
            container.grid(row=0, column=0, sticky="nsew")
            self.gallery_grid = ctk.CTkFrame(container, fg_color="transparent")
            self.gallery_grid.pack(fill="x", padx=10, pady=10)
        else:
            self.gallery_grid = ctk.CTkFrame(self.gallery_frame, fg_color="transparent")
            self.gallery_grid.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
            for c in range(cols):
                self.gallery_grid.grid_columnconfigure(c, weight=1)
            for r in range(rows):
                self.gallery_grid.grid_rowconfigure(r, weight=1)

        for idx, path in enumerate(paths):
            row = idx // cols
            col = idx % cols
            self.create_image_card(self.gallery_grid, path, row, col)

        self.focused_image_index = 0
        self._update_image_focus()
        self.update_delete_btn()
        self._update_compare_btn()
        self._update_recommendation_panel(paths)

    def create_image_card(self, parent, path, row, col):
        frame = ctk.CTkFrame(parent, border_width=2, border_color=APP_BORDER, corner_radius=10)
        frame.grid(row=row, column=col, padx=15, pady=15, sticky="nsew")
        
        # Get File Stats
        try:
            size = os.path.getsize(path)
            mtime = os.path.getmtime(path)
            date_str = datetime.datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
            size_str = self.format_size(size)
        except:
            date_str = "Unknown"
            size_str = "Unknown"
            size = 0
            mtime = 0

        # Get quality score
        score = self.image_scores.get(path, 0)
        score_color = get_score_color(score)

        # Image Thumbnail (placeholder; loaded on background thread)
        thumb_size = self.thumb_size
        img_container = ctk.CTkButton(
            frame, text="Loading…", fg_color=APP_INPUT,
            hover_color=BTN_HOVER, border_width=2, border_color=APP_BORDER,
            width=thumb_size[0], height=thumb_size[1],
            command=lambda p=path: self.manual_toggle(p),
        )
        img_container.pack(pady=10)

        def _apply_thumb(pil_img: Image.Image):
            if not frame.winfo_exists():
                return
            try:
                ctk_img = ctk.CTkImage(light_image=pil_img, size=thumb_size)
                img_container.configure(image=ctk_img, text="")
                img_container.image = ctk_img
            except (OSError, ValueError, tk.TclError) as exc:
                logging.debug("Thumb UI update failed for %s: %s", path, exc)

        def _load_thumb_worker():
            try:
                if path.lower().endswith((".mov", ".mp4")):
                    img = Image.new("RGB", thumb_size, color=BTN_ACTIVE)
                    d = ImageDraw.Draw(img)
                    d.text((10, 10), "VIDEO FILE", fill="white")
                else:
                    with Image.open(path) as pil_src:
                        pil_img = pil_src.copy()
                    pil_img.thumbnail(thumb_size, Image.Resampling.LANCZOS)
                    img = Image.new("RGB", thumb_size, color=APP_INPUT)
                    img.paste(
                        pil_img,
                        ((thumb_size[0] - pil_img.width) // 2, (thumb_size[1] - pil_img.height) // 2),
                    )
                self.after(0, lambda: _apply_thumb(img))
            except (OSError, ValueError) as exc:
                logging.warning("Thumbnail failed for %s: %s", path, exc)
                self.after(0, lambda: img_container.configure(text="Error Loading\nImage"))

        threading.Thread(target=_load_thumb_worker, daemon=True).start()

        # Info Frame
        info_frame = ctk.CTkFrame(frame, fg_color="transparent")
        info_frame.pack(fill="x", pady=(0, 5), padx=10)
        
        # File name (truncated if too long)
        filename = os.path.basename(path)
        if len(filename) > 30:
            filename = filename[:27] + "..."
        ctk.CTkLabel(info_frame, text=filename, font=("Arial", 11, "bold")).pack(anchor="w")
        
        # Quality Score (prominent display)
        score_frame = ctk.CTkFrame(info_frame, fg_color=score_color, corner_radius=5)
        score_frame.pack(fill="x", pady=(5, 0))
        score_label = ctk.CTkLabel(
            score_frame, text=f"⭐ Quality Score: {score:.1f}",
            text_color="white", font=("Arial", 10, "bold"),
        )
        score_label.pack(pady=2)
        
        # Date and size
        ctk.CTkLabel(info_frame, text=f"📅 {date_str}", font=("Arial", 10)).pack(anchor="w", pady=(2, 0))
        ctk.CTkLabel(info_frame, text=f"📏 {size_str}", font=("Arial", 10)).pack(anchor="w", pady=(2, 0))
        
        # Path (truncated)
        dir_path = os.path.dirname(path)
        if len(dir_path) > 40:
            dir_path = "..." + dir_path[-37:]
        ctk.CTkLabel(info_frame, text=f"📁 {dir_path}", font=("Arial", 9), text_color="gray").pack(anchor="w", pady=(2, 5))

        # Checkbox (Marked for deletion)
        del_var = ctk.BooleanVar(value=False)
        chk = ctk.CTkCheckBox(frame, text="Mark for Deletion", variable=del_var, 
                              command=lambda p=path: self.handle_checkbox(p, del_var), 
                              checkbox_width=20, checkbox_height=20, 
                              fg_color=APP_DANGER, hover_color=APP_DANGER_HOVER)
        chk.pack(pady=10)
        
        # Store meta data
        frame.meta_data = {
            "path": path, 
            "var": del_var, 
            "size": size, 
            "mtime": mtime,
            "score": score,
            "img_container": img_container,
            "score_frame": score_frame,
            "score_label": score_label,
            "frame": frame
        }

    def format_size(self, size_bytes):
        if size_bytes == 0:
            return "0 B"
        units = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
        i = 0
        size = float(size_bytes)
        while size >= 1024 and i < len(units) - 1:
            size /= 1024
            i += 1
        return f"{size:.2f} {units[i]}"

    def manual_toggle(self, path):
        # Triggered by clicking image
        for widget in self._iter_gallery_cards():
            if widget.meta_data["path"] == path:
                current_val = widget.meta_data["var"].get()
                widget.meta_data["var"].set(not current_val)
                self.handle_checkbox(path, widget.meta_data["var"])
                break

    def handle_checkbox(self, path, var):
        # Update visual feedback
        for widget in self._iter_gallery_cards():
            if widget.meta_data["path"] == path:
                if var.get():
                    self.files_to_delete.add(path)
                    widget.configure(border_color=APP_DANGER)
                    if widget.meta_data["img_container"]:
                        widget.meta_data["img_container"].configure(border_color=APP_DANGER)
                else:
                    self.files_to_delete.discard(path)
                    widget.configure(border_color="gray")
                    if widget.meta_data["img_container"]:
                        widget.meta_data["img_container"].configure(border_color="gray")
                break

        self._update_image_focus()
        self.update_delete_btn()
        self._update_compare_btn()

    def _marked_paths(self) -> list[str]:
        marked = []
        for widget in self._iter_gallery_cards():
            if widget.meta_data["var"].get():
                marked.append(widget.meta_data["path"])
        return marked

    def _update_compare_btn(self):
        marked = self._marked_paths()
        if len(marked) == 2:
            self.compare_btn.configure(state="normal")
        else:
            self.compare_btn.configure(state="disabled")

    def compare_selected(self):
        marked = self._marked_paths()
        if len(marked) != 2:
            messagebox.showinfo("Compare", "Mark exactly two files in this group to compare.")
            return "break"
        SideBySideCompareDialog(self, marked[0], marked[1])
        return "break"

    def update_delete_btn(self):
        count = len(self.files_to_delete)
        self.delete_btn.configure(text=f"🗑 Delete {count} selected")
        if count > 0:
            self.delete_btn.configure(
                state="normal",
                fg_color=APP_DANGER,
                hover_color=APP_DANGER_HOVER,
                text_color=APP_PRIMARY_TEXT,
            )
        else:
            self.delete_btn.configure(
                state="disabled",
                fg_color=APP_BTN_DISABLED_FG,
                hover_color=APP_BTN_DISABLED_FG,
                text_color=APP_BTN_DISABLED_TEXT,
            )

    def smart_select(self, mode):
        if not self.current_group_files or len(self.current_group_files) < 2:
            messagebox.showinfo("No Selection", "Please select a group with duplicates first.")
            return
        
        widgets = list(self._iter_gallery_cards())
        
        if mode == "clear":
            for w in widgets:
                w.meta_data["var"].set(False)
                self.handle_checkbox(w.meta_data["path"], w.meta_data["var"])
            return

        if mode == "all":
            for w in widgets:
                w.meta_data["var"].set(True)
                self.handle_checkbox(w.meta_data["path"], w.meta_data["var"])
            return

        # Determine which file to KEEP (others will be marked for deletion)
        keep_path = None
        
        if mode == "smart_best":
            # Enhanced logic: use quality score, then file size, then date
            best_widget = None
            best_score = -1
            
            for w in widgets:
                score = w.meta_data.get("score", 0)
                size = w.meta_data.get("size", 0)
                mtime = w.meta_data.get("mtime", 0)
                
                # Combined scoring: quality (60%), size (25%), recency (15%)
                combined_score = score * 0.6 + (size / (1024*1024)) * 0.25 + (mtime / 1000000) * 0.15
                
                if combined_score > best_score:
                    best_score = combined_score
                    best_widget = w
            
            if best_widget:
                keep_path = best_widget.meta_data["path"]
                
        elif mode == "keep_newest":
            # Keep the newest file (largest mtime)
            keep_path = max(widgets, key=lambda w: w.meta_data["mtime"]).meta_data["path"]
            
        elif mode == "keep_oldest":
            # Keep the oldest file (smallest mtime)
            keep_path = min(widgets, key=lambda w: w.meta_data["mtime"]).meta_data["path"]
            
        elif mode == "keep_largest":
            # Keep the largest file
            keep_path = max(widgets, key=lambda w: w.meta_data["size"]).meta_data["path"]
            
        elif mode == "keep_smallest":
            # Keep the smallest file
            keep_path = min(widgets, key=lambda w: w.meta_data["size"]).meta_data["path"]
        
        # Apply selection: mark all for deletion except the one to keep
        reason = self._build_keep_reason(keep_path, widgets, mode)
        for w in widgets:
            if w.meta_data["path"] == keep_path:
                w.meta_data["var"].set(False)  # Don't delete this one
            else:
                w.meta_data["var"].set(True)  # Delete this one
            self.handle_checkbox(w.meta_data["path"], w.meta_data["var"])
        if reason:
            self.recommendation_panel.grid()
            self.recommendation_label.configure(text=reason)

    def _build_keep_reason(self, keep_path, widgets, mode: str) -> str:
        if not keep_path:
            return ""
        keep = next((w for w in widgets if w.meta_data["path"] == keep_path), None)
        if not keep:
            return ""
        name = os.path.basename(keep_path)
        score = keep.meta_data.get("score", 0)
        size = keep.meta_data.get("size", 0)
        mtime = keep.meta_data.get("mtime", 0)
        date_str = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d") if mtime else "unknown"
        reasons = [f"Keep: {name}"]
        if mode == "smart_best":
            reasons.append(f"quality score {score:.1f}")
            reasons.append(f"size {self.format_size(size)}")
            reasons.append(f"date {date_str}")
        elif mode == "keep_newest":
            reasons.append(f"newest file ({date_str})")
        elif mode == "keep_oldest":
            reasons.append(f"oldest file ({date_str})")
        elif mode == "keep_largest":
            reasons.append(f"largest file ({self.format_size(size)})")
        elif mode == "keep_smallest":
            reasons.append(f"smallest file ({self.format_size(size)})")
        marked = len(widgets) - 1
        reasons.append(f"marked {marked} lower-quality duplicate(s) for deletion")
        return " · ".join(reasons)

    def _update_recommendation_panel(self, paths: list[str]):
        if not paths:
            self.recommendation_panel.grid_remove()
            return
        best_path = max(paths, key=lambda p: self.image_scores.get(p, 0))
        score = self.image_scores.get(best_path, 0)
        try:
            size = os.path.getsize(best_path)
        except OSError:
            size = 0
        name = os.path.basename(best_path)
        text = (
            f"Recommendation: keep {name} — quality {score:.1f}, "
            f"size {self.format_size(size)}. Use Smart Best to auto-select lower scores."
        )
        self.recommendation_panel.grid()
        self.recommendation_label.configure(text=text)

    def confirm_delete(self):
        count = len(self.files_to_delete)
        if count == 0:
            return
            
        # Show confirmation with file list
        file_list = "\n".join([f"• {os.path.basename(p)}" for p in list(self.files_to_delete)[:10]])
        if count > 10:
            file_list += f"\n• ... and {count - 10} more files"
        
        if messagebox.askyesno("Confirm Delete", 
                               f"Move {count} selected files to quarantine?\n\n"
                               f"Files to delete:\n{file_list}\n\n"
                               f"Ctrl+Z undoes the last delete. A snapshot is saved if enabled in Settings."):
            self.perform_deletion()

    def perform_deletion(self):
        from snapshots import create_snapshot
        from app_settings import load_app_settings

        errors = []
        deleted = 0
        paths = list(self.files_to_delete)
        settings = load_app_settings()

        progress_window = ctk.CTkToplevel(self)
        progress_window.title("Deleting Files")
        progress_window.geometry("400x150")
        progress_window.transient(self)
        progress_window.grab_set()
        
        ctk.CTkLabel(progress_window, text="Moving files to quarantine…", font=("Arial", 14)).pack(pady=20)
        progress_bar = ctk.CTkProgressBar(progress_window, width=350)
        progress_bar.pack(pady=10)
        progress_bar.set(0)
        
        status_label = ctk.CTkLabel(progress_window, text="")
        status_label.pack(pady=10)
        
        total_files = len(paths)

        if settings.snapshot_before_delete and paths:
            try:
                status_label.configure(text="Creating safety snapshot…")
                progress_window.update()
                create_snapshot(
                    f"Before delete ({total_files} files)",
                    paths,
                    on_progress=lambda i, t, p: status_label.configure(
                        text=f"Snapshot {i}/{t}: {os.path.basename(p)}",
                    ),
                )
            except Exception as exc:
                errors.append(f"Snapshot failed: {exc}")
        
        file_ops = self._get_file_ops()
        if not file_ops:
            messagebox.showerror("Delete", "File operation service unavailable.")
            return

        for i, path in enumerate(paths):
            try:
                progress_bar.set((i + 1) / max(total_files, 1))
                status_label.configure(text=f"Quarantine: {os.path.basename(path)}")
                progress_window.update()

                ok, detail = file_ops.delete(path)
                if not ok:
                    errors.append(f"{os.path.basename(path)}: {detail}")
                    continue
                deleted += 1

                if path in self.current_group_files:
                    self.current_group_files.remove(path)

            except Exception as e:
                errors.append(f"{os.path.basename(path)}: {str(e)}")
        
        progress_window.destroy()
        
        # Show results
        result_msg = f"Successfully deleted {deleted} files."
        if errors:
            error_list = "\n".join(errors[:5])
            if len(errors) > 5:
                error_list += f"\n... and {len(errors) - 5} more errors"
            result_msg += f"\n\nErrors encountered:\n{error_list}"
        
        messagebox.showinfo("Deletion Complete", result_msg)
        
        # Update UI
        self.status_label.configure(text=f"Deleted {deleted} files. Refresh to see changes.")
        self.files_to_delete = set()
        self.update_delete_btn()
        
        # Reload current group if it still has files
        if self.current_group_files:
            self.load_group(self.current_group_hash, self.current_group_files, self.current_selected_group)

