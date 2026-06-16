"""
Media Gallery — browse photos, edit metadata, filter, rate, and view in-app.
Separate from the duplicate-review gallery in DuplicateView.
"""
import datetime
import logging
import os
import threading
from tkinter import filedialog, messagebox
from typing import Callable, Optional

import customtkinter as ctk
from PIL import Image

from app_settings import (
    DEFAULT_SIDECAR_MAPPING,
    SIDECAR_FIELD_LABELS,
    load_app_settings,
    load_sidecar_mapping,
    mapping_from_display,
    mapping_to_display,
    save_app_settings,
)
from media_viewer import (
    EmbeddedImageViewer, LightboxViewer, SideBySideCompareDialog, load_oriented_image,
    pil_to_ctk_image, rating_stars_text,
)
from duplicate_utils import find_similar_paths
from views.helpers import calculate_perceptual_hash, HAS_IMAGEHASH
from metadata_tools import (
    ImageMetadata,
    apply_autodetected_metadata,
    apply_rename_plan,
    batch_autodetect_plan,
    bulk_rename_plan,
    collect_tags,
    display_tags,
    export_metadata_csv,
    export_metadata_json,
    filter_files,
    find_sidecar,
    find_sidecar_pairs,
    format_rename_preview,
    format_detection_summary,
    list_gallery_media,
    list_images,
    merge_all_sidecars,
    merge_sidecar_into_image,
    merge_sidecar_pairs,
    read_metadata,
    scan_gallery_metadata,
    sidecar_preview,
    write_metadata,
)
from media_index import sync_and_list
from ocr_index import (
    build_index,
    capability_hint,
    index_exists,
    index_stats,
    is_indexable,
    search_index,
)
from video_thumbs import extract_video_thumbnail, ffmpeg_available, is_video_file
from smart_playlists import PlaylistStore, SmartPlaylist
from gps_utils import open_in_browser, osm_url
from takeout_import import discover_takeout_albums, find_takeout_sidecar, import_takeout_album
from design_system import (
    ElevatedCard, GhostButton, LabeledEntry, PageHeader, PrimaryButton, SecondaryButton,
    StyledCheckBox, StyledOptionMenu,
)
from theme import (
    APP_ACCENT, APP_ACCENT_HOVER, APP_BORDER, APP_CARD, APP_PRIMARY_TEXT, APP_SECONDARY, APP_SECONDARY_HOVER,
    APP_SUCCESS, APP_SUCCESS_HOVER, APP_TEXT, APP_TEXT_MUTED, BTN_ACTIVE, CONTENT_MARGIN, ERROR, FONT_MONO_SM,
    GALLERY_SORT_OPTIONS, INPUT_BG, INPUT_RADIUS, SECTION_GAP, SIDEBAR_TILE_ACTIVE, WINDOW_BG,
)
from ui_components import EmptyState, GALLERY_SHORTCUTS
from i18n import t

THUMB_SIZE = (150, 150)
EMBEDDED_MIN_H = 320


class StarRatingWidget(ctk.CTkFrame):
    """Clickable 0-5 star row."""

    def __init__(self, parent, on_change=None, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.on_change = on_change
        self._rating = 0
        self._buttons: list[ctk.CTkButton] = []
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x")
        ctk.CTkLabel(row, text="Rating", width=80, anchor="w").pack(side="left")
        for i in range(1, 6):
            btn = ctk.CTkButton(
                row, text="*", width=32, height=28,
                fg_color=INPUT_BG, hover_color=SIDEBAR_TILE_ACTIVE,
                command=lambda n=i: self.set_rating(n, notify=True),
            )
            btn.pack(side="left", padx=2)
            self._buttons.append(btn)
        GhostButton(
            row, text="Clear", width=50,
            command=lambda: self.set_rating(0, notify=True),
        ).pack(side="left", padx=(8, 0))

    def set_rating(self, rating: int, notify: bool = False):
        self._rating = max(0, min(5, rating))
        for i, btn in enumerate(self._buttons, start=1):
            if i <= self._rating:
                btn.configure(
                    fg_color=APP_ACCENT, text_color=APP_PRIMARY_TEXT,
                    hover_color=APP_ACCENT_HOVER,
                )
            else:
                btn.configure(
                    fg_color=INPUT_BG, text_color=APP_TEXT_MUTED,
                    hover_color=BTN_ACTIVE,
                )
        if notify and self.on_change:
            self.on_change(self._rating)

    def get_rating(self) -> int:
        return self._rating


class SidecarMappingDialog(ctk.CTkToplevel):
    """Edit JSON/XMP sidecar field mapping (comma-separated source keys per target field)."""

    def __init__(self, parent, on_saved: Optional[Callable[[], None]] = None):
        super().__init__(parent)
        self.on_saved = on_saved
        self.title("Sidecar field mapping")
        self.geometry("620x420")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.configure(fg_color=WINDOW_BG)

        settings = load_app_settings()
        display = mapping_to_display(settings.sidecar_field_mapping)
        self._vars: dict[str, ctk.StringVar] = {}

        ctk.CTkLabel(
            self,
            text="Map sidecar keys to metadata fields. Use comma-separated names.\n"
                 "Works for JSON keys and XMP tags (e.g. dc:description, xmp:Rating).",
            font=ctk.CTkFont(size=12), text_color=APP_TEXT_MUTED, justify="left",
        ).pack(fill="x", padx=16, pady=(16, 10))

        form = ctk.CTkScrollableFrame(self, fg_color="transparent", height=240)
        form.pack(fill="both", expand=True, padx=16, pady=4)
        for key, label in SIDECAR_FIELD_LABELS.items():
            row = ctk.CTkFrame(form, fg_color="transparent")
            row.pack(fill="x", pady=4)
            ctk.CTkLabel(row, text=label, width=150, anchor="w").pack(side="left")
            var = ctk.StringVar(value=display.get(key, ""))
            self._vars[key] = var
            ctk.CTkEntry(row, textvariable=var).pack(side="left", fill="x", expand=True)

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=16)
        SecondaryButton(btn_row, text="Reset defaults", width=120, command=self._reset_defaults).pack(side="left")
        SecondaryButton(btn_row, text="Cancel", width=90, command=self.destroy).pack(side="right", padx=(8, 0))
        PrimaryButton(btn_row, text="Save", width=90, command=self._save).pack(side="right")

    def _reset_defaults(self):
        display = mapping_to_display(DEFAULT_SIDECAR_MAPPING)
        for key, var in self._vars.items():
            var.set(display.get(key, ""))

    def _save(self):
        settings = load_app_settings()
        settings.sidecar_field_mapping = mapping_from_display(
            {key: var.get() for key, var in self._vars.items()}
        )
        save_app_settings(settings)
        if self.on_saved:
            self.on_saved()
        self.destroy()


class SidecarMergeDialog(ctk.CTkToplevel):
    """Review sidecar pairs with checkboxes before merging into images."""

    def __init__(
        self,
        parent,
        pairs: list[tuple[str, str]],
        mapping: dict[str, list[str]],
        delete_sidecar: bool = False,
        on_done: Optional[Callable[[], None]] = None,
        on_toast: Optional[Callable[[str], None]] = None,
        on_mapping: Optional[Callable[[], None]] = None,
    ):
        super().__init__(parent)
        self.pairs = pairs
        self.mapping = mapping
        self.on_done = on_done
        self.on_toast = on_toast
        self.on_mapping = on_mapping
        self._checks: list[tuple[ctk.BooleanVar, tuple[str, str]]] = []

        self.title("Review sidecar merge")
        self.geometry("720x520")
        self.minsize(600, 400)
        self.transient(parent)
        self.grab_set()
        self.configure(fg_color=WINDOW_BG)

        ctk.CTkLabel(
            self,
            text=f"{len(pairs)} image + sidecar pair(s) found. "
                 "Review what will be embedded into EXIF, then merge.",
            font=ctk.CTkFont(size=13), text_color=APP_TEXT_MUTED, justify="left",
        ).pack(fill="x", padx=16, pady=(16, 8))

        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=16, pady=(0, 8))
        SecondaryButton(toolbar, text="Select all", width=90, command=self._select_all).pack(side="left", padx=(0, 6))
        SecondaryButton(toolbar, text="Clear all", width=90, command=self._clear_all).pack(side="left")
        if on_mapping:
            SecondaryButton(
                toolbar, text="Field mapping", width=110, command=on_mapping,
            ).pack(side="right")

        self.list_frame = ctk.CTkScrollableFrame(self, fg_color=INPUT_BG, height=320)
        self.list_frame.pack(fill="both", expand=True, padx=16, pady=4)

        for image_path, sidecar_path in pairs:
            self._add_pair_row(image_path, sidecar_path)

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=16, pady=16)
        self.delete_var = ctk.BooleanVar(value=delete_sidecar)
        ctk.CTkCheckBox(footer, text="Delete sidecar after successful merge", variable=self.delete_var).pack(
            side="left",
        )
        SecondaryButton(footer, text="Cancel", width=90, command=self.destroy).pack(side="right", padx=(8, 0))
        PrimaryButton(
            footer, text="Merge checked", width=130, command=self._merge_checked,
        ).pack(side="right", padx=(8, 0))

    def _add_pair_row(self, image_path: str, sidecar_path: str):
        row = ctk.CTkFrame(self.list_frame, fg_color=APP_CARD, corner_radius=8,
                           border_width=1, border_color=APP_BORDER)
        row.pack(fill="x", padx=4, pady=4)

        var = ctk.BooleanVar(value=True)
        self._checks.append((var, (image_path, sidecar_path)))

        head = ctk.CTkFrame(row, fg_color="transparent")
        head.pack(fill="x", padx=10, pady=(8, 2))
        ctk.CTkCheckBox(
            head,
            text=f"{os.path.basename(image_path)}  +  {os.path.basename(sidecar_path)}",
            variable=var,
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(side="left", anchor="w")

        preview = sidecar_preview(sidecar_path, self.mapping)
        ctk.CTkLabel(
            row, text=preview, font=FONT_MONO_SM, text_color=APP_TEXT_MUTED,
            anchor="w", justify="left", wraplength=640,
        ).pack(fill="x", padx=28, pady=(0, 10))

    def _select_all(self):
        for var, _ in self._checks:
            var.set(True)

    def _clear_all(self):
        for var, _ in self._checks:
            var.set(False)

    def _selected_pairs(self) -> list[tuple[str, str]]:
        return [pair for var, pair in self._checks if var.get()]

    def _merge_checked(self):
        selected = self._selected_pairs()
        if not selected:
            messagebox.showinfo("Sidecar merge", "Check at least one pair to merge.")
            return
        delete = self.delete_var.get()
        if delete and not messagebox.askyesno(
            "Delete sidecars?",
            f"Merge {len(selected)} pair(s) and delete the sidecar files afterward?",
        ):
            return
        merged, failed, errors = merge_sidecar_pairs(
            selected, delete_sidecar=delete, mapping=self.mapping,
        )
        if merged:
            msg = f"Merged {merged} sidecar(s) into images."
            if failed:
                msg += f" {failed} failed."
            if self.on_toast:
                self.on_toast(msg)
            if self.on_done:
                self.on_done()
            self.destroy()
            if errors:
                messagebox.showwarning("Sidecar merge", msg + "\n\n" + "\n".join(errors[:6]))
        else:
            detail = "\n".join(errors[:6]) if errors else "Nothing was merged."
            messagebox.showerror("Sidecar merge", detail)


class MediaGalleryView(ctk.CTkFrame):
    """Library browser: thumbnails, metadata, filters, ratings, in-app viewer."""

    def __init__(
        self,
        parent,
        library_root: str = "",
        on_toast: Optional[Callable[[str], None]] = None,
        on_status: Optional[Callable[..., None]] = None,
        shortcut_manager=None,
        metadata_provider=None,
    ):
        super().__init__(parent, fg_color="transparent")

        self._library_root = library_root.strip()
        self._on_toast = on_toast
        self._on_status = on_status
        self._shortcut_manager = shortcut_manager
        if metadata_provider is not None:
            self._metadata = metadata_provider
        else:
            from services.metadata_provider import MetadataProvider
            self._metadata = MetadataProvider()
        self._metadata.on_update(self._on_metadata_updated)
        self._app_settings = load_app_settings()
        self.folder_var = ctk.StringVar()
        self.event_var = ctk.StringVar()
        self.caption_var = ctk.StringVar()
        self.keywords_var = ctk.StringVar()
        self.event_meta_var = ctk.StringVar()
        self.date_var = ctk.StringVar()
        self.search_var = ctk.StringVar()
        self.recursive_var = ctk.BooleanVar(value=False)
        self.exif_date_var = ctk.BooleanVar(value=True)
        self.match_all_var = ctk.BooleanVar(value=False)
        self.delete_sidecar_var = ctk.BooleanVar(value=False)
        self.tag_filter_var = ctk.StringVar(value="(all tags)")
        self.min_rating_var = ctk.StringVar(value="0+")
        self.date_from_var = ctk.StringVar(value="")
        self.date_to_var = ctk.StringVar(value="")
        self.sort_var = ctk.StringVar(value=self._app_settings.gallery_sort)
        self._metadata_collapsed = self._app_settings.metadata_panel_collapsed

        self._all_files: list[str] = []
        self._files: list[str] = []
        self._meta_cache: dict[str, ImageMetadata] = {}
        self._selected: Optional[str] = None
        self._thumb_refs: list = []
        self._thumb_cards: dict[str, ctk.CTkFrame] = {}
        self._rendered_paths: tuple[str, ...] = ()
        self._loading = False
        self._rename_plan: list[tuple[str, str]] = []
        self._lightbox: Optional[LightboxViewer] = None
        self._filling_form = False
        self._autosave_job: Optional[str] = None
        self._sidecar_mapping = load_sidecar_mapping()
        self._gallery_key_bindings: list = []
        self._playlist_store = PlaylistStore.load()
        self.playlist_var = ctk.StringVar(value="(no playlist)")
        self._ocr_indexing = False
        self._ocr_extra_files: list[str] = []
        self._phash_cache: dict[str, str] = {}
        self._compare_anchor: Optional[str] = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        PageHeader(
            self,
            title="Media Gallery",
            subtitle="Browse, rate, filter by tags, edit EXIF metadata, and view photos in-app. "
                     "Duplicate review keeps its own comparison gallery.",
        ).grid(row=0, column=0, sticky="ew", pady=(0, SECTION_GAP))

        toolbar_card = ElevatedCard(self)
        toolbar_card.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        toolbar = toolbar_card.body
        toolbar.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(toolbar, text="Folder", font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=0, column=0, padx=12, pady=12, sticky="w")
        LabeledEntry(
            toolbar, textvariable=self.folder_var, placeholder_text="Photo folder or event album",
        ).grid(row=0, column=1, padx=8, pady=12, sticky="ew")
        SecondaryButton(toolbar, text="Browse", width=80, command=self.browse_folder).grid(row=0, column=2, padx=4, pady=12)
        PrimaryButton(toolbar, text="Load", width=70, command=self.load_folder).grid(row=0, column=3, padx=4, pady=12)
        SecondaryButton(toolbar, text="Library", width=70, command=self.open_library_root).grid(row=0, column=4, padx=4, pady=12)
        StyledCheckBox(toolbar, text="Subfolders", variable=self.recursive_var).grid(row=0, column=5, padx=8, pady=12)
        self.count_label = ctk.CTkLabel(toolbar, text="", text_color=APP_TEXT_MUTED)
        self.count_label.grid(row=0, column=6, padx=12, pady=12)

        filters_card = ElevatedCard(self)
        filters_card.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        filters = filters_card.body
        filters.grid_columnconfigure(5, weight=1)

        ctk.CTkLabel(filters, text="Tag", width=40).grid(row=0, column=0, padx=(12, 4), pady=10)
        self.tag_menu = StyledOptionMenu(
            filters, variable=self.tag_filter_var, values=["(all tags)"],
            command=lambda _: self.apply_filters(), width=120,
        )
        self.tag_menu.grid(row=0, column=1, padx=4, pady=10)
        ctk.CTkLabel(filters, text="Min stars", width=60).grid(row=0, column=2, padx=(8, 4), pady=10)
        StyledOptionMenu(
            filters, variable=self.min_rating_var,
            values=["0+", "1+", "2+", "3+", "4+", "5"],
            command=lambda _: self.apply_filters(), width=70,
        ).grid(row=0, column=3, padx=4, pady=10, sticky="w")
        ctk.CTkLabel(filters, text="Sort", width=36).grid(row=0, column=4, padx=(8, 4), pady=10)
        self.sort_menu = StyledOptionMenu(
            filters, variable=self.sort_var, values=list(GALLERY_SORT_OPTIONS),
            command=self._on_sort_changed, width=130,
        )
        self.sort_menu.grid(row=0, column=5, padx=4, pady=10, sticky="w")
        LabeledEntry(
            filters, textvariable=self.search_var,
            placeholder_text="Search filename, caption, tags, OCR text…", width=180,
        ).grid(row=0, column=6, padx=8, pady=10, sticky="ew")
        filters.grid_columnconfigure(6, weight=1)
        StyledCheckBox(filters, text="Match all tags", variable=self.match_all_var,
                       command=self.apply_filters).grid(row=0, column=7, padx=4, pady=10)
        SecondaryButton(filters, text="Search", width=70, command=self.apply_filters).grid(
            row=0, column=8, padx=4, pady=10)
        GhostButton(filters, text="Clear", width=60, command=self.clear_filters).grid(
            row=0, column=9, padx=(4, 4), pady=10)
        SecondaryButton(filters, text="Export CSV", width=90, command=self.export_csv).grid(
            row=0, column=10, padx=4, pady=10)
        SecondaryButton(filters, text="Export JSON", width=90, command=self.export_json).grid(
            row=0, column=11, padx=4, pady=10)
        PrimaryButton(
            filters, text="Autodetect wizard", width=120,
            command=self.open_autodetect_wizard,
        ).grid(row=0, column=12, padx=(4, 12), pady=10)

        ctk.CTkLabel(filters, text="Playlist", width=52).grid(row=1, column=0, padx=(12, 4), pady=(0, 10))
        self.playlist_menu = StyledOptionMenu(
            filters, variable=self.playlist_var, values=self._playlist_names(),
            command=self._on_playlist_selected, width=140,
        )
        self.playlist_menu.grid(row=1, column=1, padx=4, pady=(0, 10), sticky="w")
        SecondaryButton(filters, text="Save filters", width=90, command=self._save_playlist).grid(
            row=1, column=2, padx=4, pady=(0, 10))
        SecondaryButton(
            filters, text="Build search index", width=130,
            command=self.build_ocr_index,
        ).grid(row=1, column=3, padx=4, pady=(0, 10))
        self.ocr_status_label = ctk.CTkLabel(
            filters, text=self._ocr_status_text(), font=ctk.CTkFont(size=11),
            text_color=APP_TEXT_MUTED, wraplength=520, justify="left",
        )
        GhostButton(filters, text="Map view", width=80, command=self.open_map_view).grid(
            row=1, column=4, padx=4, pady=(0, 10))
        SecondaryButton(filters, text="Takeout merge", width=110, command=self.merge_takeout_folder).grid(
            row=1, column=5, padx=4, pady=(0, 10))
        SecondaryButton(filters, text="Takeout albums", width=110, command=self.import_takeout_albums).grid(
            row=1, column=6, padx=4, pady=(0, 10))
        SecondaryButton(filters, text="Compare", width=80, command=self.open_side_by_side_compare).grid(
            row=1, column=7, padx=4, pady=(0, 10))
        SecondaryButton(filters, text="Find similar", width=100, command=self.find_similar_images).grid(
            row=1, column=8, padx=4, pady=(0, 10))
        ctk.CTkLabel(filters, text="From", width=36).grid(row=2, column=0, padx=(12, 2), pady=(0, 8))
        LabeledEntry(filters, textvariable=self.date_from_var, placeholder_text="YYYY-MM-DD", width=100).grid(
            row=2, column=1, padx=2, pady=(0, 8), sticky="w")
        ctk.CTkLabel(filters, text="To", width=24).grid(row=2, column=2, padx=(4, 2), pady=(0, 8))
        LabeledEntry(filters, textvariable=self.date_to_var, placeholder_text="YYYY-MM-DD", width=100).grid(
            row=2, column=3, padx=2, pady=(0, 8), sticky="w")
        self.ocr_status_label.grid(row=3, column=0, columnspan=12, padx=12, pady=(0, 10), sticky="w")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=3, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(0, weight=1)

        gallery_elevated = ElevatedCard(body)
        gallery_elevated.grid(row=0, column=0, padx=(0, 8), sticky="nsew")
        gallery_card = gallery_elevated.body
        gallery_card.grid_rowconfigure(1, weight=1)
        gallery_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(gallery_card, text="Photos & videos", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, padx=4, pady=(0, 6), sticky="w")
        self.gallery_scroll = ctk.CTkScrollableFrame(gallery_card, fg_color=INPUT_BG)
        self.gallery_scroll.grid(row=1, column=0, padx=4, pady=(0, 4), sticky="nsew")
        self.gallery_grid = ctk.CTkFrame(self.gallery_scroll, fg_color="transparent")
        self.gallery_grid.pack(fill="x", expand=True)
        self.gallery_empty = EmptyState(
            self.gallery_scroll,
            icon="🖼️",
            title="No media loaded",
            subtitle="Browse or enter a folder path, then click Load.",
            action_text="Browse folder",
            action=self.browse_folder,
        )
        self.gallery_empty.pack(pady=60)

        side_elevated = ElevatedCard(body)
        side_elevated.grid(row=0, column=1, sticky="nsew")
        side = side_elevated.body
        side.grid_rowconfigure(1, weight=1)
        side.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(side, text="Viewer & metadata", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, padx=4, pady=(0, 6), sticky="w")

        side_inner = ctk.CTkScrollableFrame(side, fg_color="transparent")
        side_inner.grid(row=1, column=0, sticky="nsew", padx=0, pady=(0, 4))

        self.embedded_viewer = EmbeddedImageViewer(
            side_inner, on_fullscreen=self.open_lightbox, height=EMBEDDED_MIN_H,
        )
        self.embedded_viewer.pack(fill="x", padx=6, pady=(0, 8))

        nav = ctk.CTkFrame(side_inner, fg_color="transparent")
        nav.pack(fill="x", padx=6, pady=(0, 8))
        SecondaryButton(nav, text="Previous", width=90, command=self.select_previous).pack(side="left", padx=(0, 6))
        SecondaryButton(nav, text="Next", width=90, command=self.select_next).pack(side="left")
        self.file_label = ctk.CTkLabel(nav, text="No image selected", font=FONT_MONO_SM, text_color=APP_TEXT_MUTED)
        self.file_label.pack(side="left", padx=12)

        self.star_widget = StarRatingWidget(side_inner, on_change=self._on_star_click)
        self.star_widget.pack(fill="x", padx=6, pady=4)

        meta_header = ctk.CTkFrame(side_inner, fg_color="transparent")
        meta_header.pack(fill="x", padx=6, pady=(4, 0))
        self.metadata_toggle_btn = GhostButton(
            meta_header,
            text="▼ Metadata" if not self._metadata_collapsed else "▶ Metadata",
            width=120, height=32, anchor="w",
            command=self._toggle_metadata_panel,
        )
        self.metadata_toggle_btn.pack(side="left")

        self.metadata_body = ctk.CTkFrame(side_inner, fg_color="transparent")

        self.detect_label = ctk.CTkLabel(
            self.metadata_body, text="Select a photo to auto-fill metadata from the file.",
            font=FONT_MONO_SM, text_color=APP_TEXT_MUTED, wraplength=340, justify="left",
        )
        self.detect_label.pack(fill="x", padx=12, pady=(0, 6))

        gps_row = ctk.CTkFrame(self.metadata_body, fg_color="transparent")
        gps_row.pack(fill="x", padx=12, pady=(0, 6))
        self.gps_label = ctk.CTkLabel(
            gps_row, text="", font=FONT_MONO_SM, text_color=APP_TEXT_MUTED, anchor="w",
        )
        self.gps_label.pack(side="left", fill="x", expand=True)
        self.gps_map_btn = GhostButton(
            gps_row, text="Map", width=60, height=28,
            command=self._open_selected_on_map,
        )
        self.gps_map_btn.pack(side="right")
        self.gps_map_btn.pack_forget()

        detect_row = ctk.CTkFrame(self.metadata_body, fg_color="transparent")
        detect_row.pack(fill="x", padx=6, pady=(0, 6))
        GhostButton(
            detect_row, text="Re-detect from file", width=140, height=32,
            command=self.redetect_metadata,
        ).pack(side="left")

        form = ctk.CTkFrame(self.metadata_body, fg_color="transparent")
        form.pack(fill="x", padx=6, pady=4)
        self._form_field(form, "Date taken", self.date_var, placeholder="YYYY-MM-DD HH:MM")
        self._form_field(form, "Event", self.event_meta_var, placeholder="LondonTrip")
        self._form_field(form, "Caption", self.caption_var)
        self._form_field(form, "Keywords", self.keywords_var, placeholder="family, uk, vacation")

        save_row = ctk.CTkFrame(self.metadata_body, fg_color="transparent")
        save_row.pack(fill="x", padx=12, pady=(8, 4))
        self.auto_save_var = ctk.BooleanVar(value=self._app_settings.auto_save_metadata)
        StyledCheckBox(
            save_row, text="Auto-save metadata", variable=self.auto_save_var,
            command=self._on_auto_save_toggle,
        ).pack(side="left")
        self.save_status_label = ctk.CTkLabel(
            save_row, text="Edits save automatically", font=FONT_MONO_SM, text_color=APP_TEXT_MUTED,
        )
        self.save_status_label.pack(side="left", padx=12)
        PrimaryButton(
            save_row, text="Save now", width=90,
            command=lambda: self.save_metadata(silent=False),
        ).pack(side="right")

        for var in (self.date_var, self.event_meta_var, self.caption_var, self.keywords_var):
            var.trace_add("write", self._on_metadata_field_changed)

        bulk_elevated = ElevatedCard(self)
        bulk_elevated.grid(row=5, column=0, sticky="ew", pady=(8, 0))
        bulk = bulk_elevated.body
        bulk.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(bulk, text="Bulk rename", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, padx=4, pady=8, sticky="w")
        ctk.CTkLabel(bulk, text="Event name", width=80).grid(row=0, column=1, padx=8, sticky="w")
        LabeledEntry(bulk, textvariable=self.event_var, placeholder_text="LondonTrip").grid(
            row=0, column=2, padx=8, pady=8, sticky="ew")
        StyledCheckBox(bulk, text="Use EXIF date", variable=self.exif_date_var).grid(row=0, column=3, padx=8, pady=8)
        SecondaryButton(bulk, text="Preview rename", command=self.preview_rename, width=120).grid(
            row=0, column=4, padx=4, pady=8)
        PrimaryButton(bulk, text="Apply rename", command=self.apply_rename, width=120).grid(
            row=0, column=5, padx=(4, 4), pady=8)

        self.rename_preview = ctk.CTkTextbox(
            bulk, height=70, font=FONT_MONO_SM, fg_color=INPUT_BG, text_color=APP_TEXT_MUTED,
        )
        self.rename_preview.grid(row=1, column=0, columnspan=6, padx=4, pady=(0, 8), sticky="ew")
        self.rename_preview.insert("1.0", "Pattern: YYYYMMDD_EventName_001.jpg")
        self.rename_preview.configure(state="disabled")

        sidecar_elevated = ElevatedCard(self)
        sidecar_elevated.grid(row=6, column=0, sticky="ew", pady=(8, 0))
        sidecar = sidecar_elevated.body
        sidecar.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(sidecar, text="Sidecar merge (JSON / XMP)", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, padx=4, pady=8, sticky="w")
        self.sidecar_count_label = ctk.CTkLabel(
            sidecar, text="Load a folder to find image + sidecar pairs.",
            font=FONT_MONO_SM, text_color=APP_TEXT_MUTED, anchor="w",
        )
        self.sidecar_count_label.grid(row=0, column=1, padx=8, pady=8, sticky="ew")
        StyledCheckBox(sidecar, text="Delete sidecar after merge", variable=self.delete_sidecar_var).grid(
            row=0, column=2, padx=8, pady=8)
        SecondaryButton(sidecar, text="Field mapping", width=110, command=self.open_field_mapping).grid(
            row=0, column=3, padx=4, pady=8)
        SecondaryButton(sidecar, text="Merge selected", width=120, command=self.merge_selected_sidecar).grid(
            row=0, column=4, padx=4, pady=8)
        PrimaryButton(
            sidecar, text="Review & merge…", width=140, command=self.open_sidecar_merge_dialog,
        ).grid(row=0, column=5, padx=(4, 4), pady=8)

        if self._library_root:
            images = os.path.join(self._library_root, "03_Images")
            self.folder_var.set(images if os.path.isdir(images) else self._library_root)

        self._apply_metadata_panel_state()

    def _form_field(self, parent, label, variable, placeholder=""):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=4)
        ctk.CTkLabel(row, text=label, width=80, anchor="w").pack(side="left")
        LabeledEntry(row, textvariable=variable, placeholder_text=placeholder).pack(
            side="left", fill="x", expand=True)

    def on_view_shown(self):
        """Restore persisted UI preferences when gallery becomes visible."""
        self.apply_app_settings()
        self.bind_gallery_keys()

    def apply_app_settings(self):
        """Sync gallery UI from app_settings.json (e.g. after Settings page save)."""
        self._app_settings = load_app_settings()
        self.sort_var.set(self._app_settings.gallery_sort)
        self.auto_save_var.set(self._app_settings.auto_save_metadata)
        self._sidecar_mapping = load_sidecar_mapping()
        if self._app_settings.metadata_panel_collapsed != self._metadata_collapsed:
            self._metadata_collapsed = self._app_settings.metadata_panel_collapsed
            self._apply_metadata_panel_state()

    def rebind_shortcuts(self):
        self.bind_gallery_keys()

    def bind_gallery_keys(self):
        self.unbind_gallery_keys()
        root = self.winfo_toplevel()
        sm = self._shortcut_manager
        if sm:
            bindings = {
                "gal_prev": (lambda e: self._key_prev(), "<Left>"),
                "gal_next": (lambda e: self._key_next(), "<Right>"),
                "gal_browse": (lambda e: self.browse_folder(), "<Control-o>"),
                "gal_save": (lambda e: self.save_metadata(silent=False), "<Control-s>"),
                "gal_lightbox": (lambda e: self.open_lightbox() if self._selected else None, "<Key-f>"),
                "gal_help": (lambda e: self._show_gallery_shortcuts(), "<question>"),
            }
            for i in range(6):
                bindings[f"gal_rating_{i}"] = (
                    lambda e, n=i: self._key_set_rating(n), f"<Key-{i}>",
                )
            for action, (handler, default) in bindings.items():
                sm.bind(root, action, default, handler)
            return
        keys = {
            "<Left>": lambda e: self._key_prev(),
            "<Right>": lambda e: self._key_next(),
            "<Control-o>": lambda e: self.browse_folder(),
            "<Control-O>": lambda e: self.browse_folder(),
            "<Control-s>": lambda e: self.save_metadata(silent=False),
            "<Control-S>": lambda e: self.save_metadata(silent=False),
            "<Key-f>": lambda e: self.open_lightbox() if self._selected else None,
            "<question>": lambda e: self._show_gallery_shortcuts(),
        }
        for i in range(6):
            keys[f"<Key-{i}>"] = lambda e, n=i: self._key_set_rating(n)
        for seq, handler in keys.items():
            root.bind(seq, handler, add="+")
            self._gallery_key_bindings.append((root, seq, handler))

    def unbind_gallery_keys(self):
        root = self.winfo_toplevel()
        sm = self._shortcut_manager
        if sm:
            actions = [
                "gal_prev", "gal_next", "gal_browse", "gal_save", "gal_lightbox", "gal_help",
            ] + [f"gal_rating_{i}" for i in range(6)]
            sm.unbind_actions(root, actions)
        for root, seq, handler in self._gallery_key_bindings:
            try:
                root.unbind(seq, handler)
            except Exception:
                pass
        self._gallery_key_bindings.clear()

    def _key_prev(self):
        if self._files and self._selected:
            self.select_previous()
        return "break"

    def _key_next(self):
        if self._files and self._selected:
            self.select_next()
        return "break"

    def _key_set_rating(self, rating: int):
        if not self._selected:
            return "break"
        self.star_widget.set_rating(rating, notify=True)
        return "break"

    def _show_gallery_shortcuts(self):
        from tkinter import messagebox
        messagebox.showinfo("Media Gallery shortcuts", GALLERY_SHORTCUTS)

    def _notify_toast(self, message: str):
        if self._on_toast:
            self._on_toast(message)

    def _notify_status(self, message: str, **kwargs):
        if self._on_status:
            self._on_status(message, **kwargs)

    def _persist_ui_settings(self):
        self._app_settings.metadata_panel_collapsed = self._metadata_collapsed
        self._app_settings.gallery_sort = self.sort_var.get()
        save_app_settings(self._app_settings)

    def _toggle_metadata_panel(self):
        self._metadata_collapsed = not self._metadata_collapsed
        self._apply_metadata_panel_state()
        self._persist_ui_settings()

    def _apply_metadata_panel_state(self):
        if self._metadata_collapsed:
            self.metadata_body.pack_forget()
            self.metadata_toggle_btn.configure(text="▶ Metadata")
        else:
            self.metadata_body.pack(fill="x", padx=0, pady=0)
            self.metadata_toggle_btn.configure(text="▼ Metadata")

    def _on_sort_changed(self, _value=None):
        self._persist_ui_settings()
        self.apply_filters()

    def _get_cached_meta(self, path: str) -> ImageMetadata:
        """Return metadata from cache only (hot path — no disk reads)."""
        meta = self._meta_cache.get(path) or self._metadata.peek(path)
        if meta is not None:
            return meta
        return ImageMetadata(filepath=path, filename=os.path.basename(path))

    def _read_meta(self, path: str, *, blocking: bool = False) -> ImageMetadata:
        cached = self._meta_cache.get(path) or self._metadata.peek(path)
        if cached is not None:
            self._meta_cache[path] = cached
            return cached
        meta = self._metadata.get_sync(path) if blocking else self._metadata.get(path)
        self._meta_cache[path] = meta
        return meta

    def _on_metadata_updated(self, path: str, meta: ImageMetadata) -> None:
        self._meta_cache[path] = meta
        if self._selected == path:
            self.after(0, lambda: self._fill_form(meta))

    def _ensure_meta_cached(self, paths: list[str]) -> None:
        """Load metadata for paths missing from cache (folder load / OCR extras)."""
        missing = [p for p in paths if p not in self._meta_cache and self._metadata.peek(p) is None]
        if missing:
            self._metadata.warm_cache("", paths=missing, background=True)
        for path in paths:
            cached = self._metadata.peek(path)
            if cached is not None:
                self._meta_cache[path] = cached

    def _sort_files(self, files: list[str]) -> list[str]:
        if not files:
            return files
        sort_key = self.sort_var.get()

        def meta_for(path: str) -> ImageMetadata:
            return self._get_cached_meta(path)

        if sort_key == "Date (newest)":
            return sorted(files, key=lambda p: meta_for(p).date_taken or datetime.datetime.min, reverse=True)
        if sort_key == "Date (oldest)":
            return sorted(files, key=lambda p: meta_for(p).date_taken or datetime.datetime.max)
        if sort_key == "Name (A-Z)":
            return sorted(files, key=lambda p: os.path.basename(p).lower())
        if sort_key == "Name (Z-A)":
            return sorted(files, key=lambda p: os.path.basename(p).lower(), reverse=True)
        if sort_key == "Rating (high)":
            return sorted(files, key=lambda p: meta_for(p).rating, reverse=True)
        if sort_key == "Rating (low)":
            return sorted(files, key=lambda p: meta_for(p).rating)
        return files

    def browse_folder(self):
        initial = self.folder_var.get() or self._library_root
        path = filedialog.askdirectory(initialdir=initial if initial and os.path.isdir(initial) else None)
        if path:
            self.folder_var.set(path)

    def open_folder(self, folder: str):
        """Load a folder programmatically (e.g. from File Organizer)."""
        if folder and os.path.isdir(folder):
            self.folder_var.set(folder)
            self.load_folder()

    def open_field_mapping(self):
        SidecarMappingDialog(self.winfo_toplevel(), on_saved=self._reload_sidecar_mapping)

    def _reload_sidecar_mapping(self):
        self._sidecar_mapping = load_sidecar_mapping()
        if self._selected:
            self._show_selection(self._selected)

    def _on_auto_save_toggle(self):
        self._app_settings.auto_save_metadata = self.auto_save_var.get()
        save_app_settings(self._app_settings)
        if self.auto_save_var.get():
            self._set_save_status("Edits save automatically")
        else:
            self._set_save_status("Auto-save off — click Save now")

    def _on_metadata_field_changed(self, *_args):
        if self._filling_form or not self.auto_save_var.get() or not self._selected:
            return
        if self._autosave_job:
            self.after_cancel(self._autosave_job)
        delay = self._app_settings.auto_save_delay_ms
        self._autosave_job = self.after(delay, self._run_autosave)

    def _run_autosave(self):
        self._autosave_job = None
        if not self._selected or not self.auto_save_var.get():
            return
        self._set_save_status("Saving…")
        self.save_metadata(silent=True)

    def _set_save_status(self, text: str, *, error: bool = False, saved: bool = False):
        if error:
            color = ERROR
        elif saved:
            color = APP_ACCENT
        else:
            color = APP_TEXT_MUTED
        self.save_status_label.configure(text=text, text_color=color)

    def open_library_root(self):
        if not self._library_root or not os.path.isdir(self._library_root):
            messagebox.showinfo("Library", "Set your media library root in Inbox Watcher settings first.")
            return
        images = os.path.join(self._library_root, "03_Images")
        self.folder_var.set(images if os.path.isdir(images) else self._library_root)
        self.load_folder()

    def load_folder(self):
        folder = self.folder_var.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showerror("Error", "Select a valid folder first.")
            return
        if self._loading:
            return
        self._loading = True
        self.count_label.configure(text="Loading…")
        self._notify_status("Loading gallery folder…", clear_after_ms=None)
        recursive = self.recursive_var.get()
        threading.Thread(target=self._scan_folder, args=(folder, recursive), daemon=True).start()

    def _scan_folder(self, folder: str, recursive: bool):
        settings = load_app_settings()

        def on_index_progress(count: int, _total: int):
            self.after(0, lambda: self.count_label.configure(text=f"Indexing… {count:,}"))

        if settings.use_media_index:
            files = sync_and_list(folder, recursive=recursive, on_progress=on_index_progress)
        else:
            files = list_gallery_media(folder, recursive=recursive)
        cache = self._metadata.cache_snapshot()
        tags = collect_tags(cache) if cache else []
        self.after(0, self._on_folder_loaded, files, cache, tags)
        self._metadata.warm_cache(folder, paths=files, recursive=recursive, background=True)

    def _on_folder_loaded(self, files: list[str], cache: dict[str, ImageMetadata], tags: list[str]):
        self._all_files = files
        self._meta_cache = cache
        self._rendered_paths = ()
        self._thumb_cards.clear()
        self._phash_cache.clear()
        tag_values = ["(all tags)"] + tags
        self.tag_menu.configure(values=tag_values if tag_values else ["(all tags)"])
        self._loading = False
        folder = self.folder_var.get().strip()
        pairs = find_sidecar_pairs(folder, recursive=self.recursive_var.get()) if folder else []
        if pairs:
            self.sidecar_count_label.configure(
                text=f"{len(pairs)} image(s) have a JSON or XMP sidecar next to them.")
        else:
            self.sidecar_count_label.configure(text="No sidecars found in this folder.")
        self._notify_status(f"Loaded {len(files)} file(s)", clear_after_ms=3000)
        self._ocr_extra_files = []
        self.apply_filters()
        if load_app_settings().auto_ocr_on_folder_load and not self._ocr_indexing:
            self.build_ocr_index(silent=True)

    def _ocr_status_text(self) -> str:
        stats = index_stats()
        docs = int(stats.get("documents", 0))
        hint = str(stats.get("hint", capability_hint()))
        if docs:
            return f"OCR index: {docs} document(s) indexed · {hint}"
        return f"OCR index empty · {hint}"

    def _refresh_ocr_status(self):
        if hasattr(self, "ocr_status_label"):
            self.ocr_status_label.configure(text=self._ocr_status_text())

    def build_ocr_index(self, silent: bool = False):
        folder = self.folder_var.get().strip()
        if not folder or not os.path.isdir(folder):
            if not silent:
                messagebox.showerror("Search index", "Load a folder first.")
            return
        if self._ocr_indexing:
            return
        self._ocr_indexing = True
        self._ocr_silent = silent
        if not silent:
            self._notify_status("Building OCR search index…", clear_after_ms=None)
        recursive = self.recursive_var.get()

        def worker():
            def on_progress(done: int, total: int, path: str):
                self.after(
                    0,
                    lambda: self._notify_status(
                        f"Indexing {done}/{total}: {os.path.basename(path)}",
                        clear_after_ms=None,
                    ),
                )

            result = build_index(folder, recursive=recursive, on_progress=on_progress)
            self.after(0, self._on_ocr_index_built, result)

        threading.Thread(target=worker, daemon=True).start()

    def _on_ocr_index_built(self, result):
        self._ocr_indexing = False
        silent = getattr(self, "_ocr_silent", False)
        self._refresh_ocr_status()
        msg = (
            f"Indexed {result.indexed} new/updated file(s) "
            f"({result.skipped} unchanged or empty, {result.failed} failed)."
        )
        self._notify_status(msg, clear_after_ms=5000)
        if not silent:
            messagebox.showinfo("Search index", msg)
        if self.search_var.get().strip():
            self.apply_filters()

    def _parse_date_filter(self, text: str) -> Optional[datetime.datetime]:
        text = (text or "").strip()
        if not text:
            return None
        try:
            return datetime.datetime.strptime(text, "%Y-%m-%d")
        except ValueError:
            return None

    def _filter_params(self) -> tuple[list[str], int, bool, str, Optional[datetime.datetime], Optional[datetime.datetime]]:
        tag = self.tag_filter_var.get()
        tags = [] if tag in ("", "(all tags)") else [tag]
        min_r = self.min_rating_var.get().replace("+", "")
        try:
            min_rating = int(min_r)
        except ValueError:
            min_rating = 0
        date_from = self._parse_date_filter(self.date_from_var.get())
        date_to = self._parse_date_filter(self.date_to_var.get())
        if date_to:
            date_to = date_to.replace(hour=23, minute=59, second=59)
        return tags, min_rating, self.match_all_var.get(), self.search_var.get(), date_from, date_to

    def apply_filters(self):
        if not self._all_files:
            self._render_gallery([])
            return
        tags, min_rating, match_all, search, date_from, date_to = self._filter_params()
        candidates = list(self._all_files)
        ocr_paths: set[str] | None = None
        if search.strip() and index_exists():
            ocr_paths = search_index(search)
            folder = self.folder_var.get().strip()
            folder_abs = os.path.abspath(folder) if folder else ""
            for path in ocr_paths:
                if path not in candidates and os.path.isfile(path) and folder_abs:
                    path_abs = os.path.abspath(path)
                    if path_abs == folder_abs or path_abs.startswith(folder_abs + os.sep):
                        candidates.append(path)
            if ocr_paths:
                self._ensure_meta_cached(
                    [p for p in ocr_paths if p in candidates and p not in self._meta_cache]
                )
        self._ocr_extra_files = [p for p in candidates if p not in self._all_files]
        self._files = filter_files(
            candidates, self._meta_cache,
            tags=tags, min_rating=min_rating, match_all=match_all, search_text=search,
            ocr_paths=ocr_paths, date_from=date_from, date_to=date_to,
        )
        self._files = self._sort_files(self._files)
        self.sort_menu.configure(state="normal" if self._files else "disabled")
        self._render_gallery(self._files)

    def clear_filters(self):
        self.tag_filter_var.set("(all tags)")
        self.min_rating_var.set("0+")
        self.search_var.set("")
        self.date_from_var.set("")
        self.date_to_var.set("")
        self.match_all_var.set(False)
        self.apply_filters()

    def _render_gallery(self, files: list[str]):
        files_tuple = tuple(files)
        if files_tuple == self._rendered_paths:
            self.count_label.configure(text=f"{len(files)} / {len(self._all_files)} file(s)")
            return

        if not files:
            self._rendered_paths = ()
            self._thumb_cards.clear()
            self._thumb_refs.clear()
            for w in self.gallery_grid.winfo_children():
                w.destroy()
            if not self._all_files:
                self.gallery_empty.set_content(
                    icon="🖼️",
                    title=t("gallery.empty.title"),
                    subtitle=t("gallery.empty.subtitle"),
                    action_text=t("gallery.empty.action"),
                    action=self.browse_folder,
                )
            else:
                self.gallery_empty.set_content(
                    icon="🔎",
                    title=t("gallery.no_match.title"),
                    subtitle=t("gallery.no_match.subtitle"),
                    action_text=t("gallery.no_match.action"),
                    action=self.clear_filters,
                )
            self.gallery_empty.pack(pady=60)
            self._selected = None
            self.count_label.configure(text="0 file(s)")
            self.embedded_viewer.show_image(None)
            self.file_label.configure(text=t("gallery.no_selection"))
            self.star_widget.set_rating(0, notify=False)
            self.detect_label.configure(text=t("gallery.detect_hint"))
            return

        self.gallery_empty.pack_forget()
        new_set = set(files)
        for path in list(self._thumb_cards.keys()):
            if path not in new_set:
                self._thumb_cards[path].destroy()
                del self._thumb_cards[path]

        self._thumb_refs.clear()
        cols = 4
        for idx, path in enumerate(files):
            row, col = divmod(idx, cols)
            if path not in self._thumb_cards:
                self._create_thumb_card(path, row, col)
            else:
                card = self._thumb_cards[path]
                card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
                self.gallery_grid.grid_columnconfigure(col, weight=1)

        self._rendered_paths = files_tuple
        self.count_label.configure(text=f"{len(files)} / {len(self._all_files)} file(s)")
        if self._selected not in files:
            self._select_by_index(0)

    def _create_thumb_card(self, path: str, row: int, col: int):
        meta = self._get_cached_meta(path)

        card = ctk.CTkFrame(self.gallery_grid, fg_color=INPUT_BG, corner_radius=INPUT_RADIUS, border_width=2,
                            border_color=APP_BORDER, cursor="hand2")
        card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
        self.gallery_grid.grid_columnconfigure(col, weight=1)

        img_frame = ctk.CTkFrame(card, fg_color="transparent")
        img_frame.pack(padx=4, pady=4)

        ext = os.path.splitext(path)[1].lower()
        try:
            if is_video_file(path):
                thumb_path = extract_video_thumbnail(path)
                if thumb_path:
                    img = Image.open(thumb_path)
                else:
                    raise OSError("no video thumb")
            elif ext == ".pdf" or is_indexable(path):
                raise OSError("document icon")
            else:
                img = load_oriented_image(path)
            img.thumbnail(THUMB_SIZE, Image.Resampling.LANCZOS)
            ctk_img = pil_to_ctk_image(img)
            img.close()
            self._thumb_refs.append(ctk_img)
            ctk.CTkLabel(img_frame, text="", image=ctk_img).pack()
            if is_video_file(path):
                badge = "▶ VIDEO"
                if not ffmpeg_available():
                    badge += " (no ffmpeg)"
                ctk.CTkLabel(img_frame, text=badge, font=("Consolas", 9), text_color=APP_ACCENT).pack()
        except (OSError, ValueError) as exc:
            logging.debug("Thumb failed for %s: %s", path, exc)
            if is_video_file(path):
                label = "▶"
            elif ext == ".pdf":
                label = "PDF"
            elif is_indexable(path):
                label = "DOC"
            else:
                label = "?"
            ctk.CTkLabel(img_frame, text=label, width=120, height=120).pack()

        tag_count = len(display_tags(meta.keywords))
        badge = f"{rating_stars_text(meta.rating)}  ({tag_count} tags)" if meta.rating or tag_count else ""
        if badge:
            ctk.CTkLabel(img_frame, text=badge, font=("Consolas", 9), text_color=APP_ACCENT).pack()

        name = os.path.basename(path)
        if len(name) > 22:
            name = name[:19] + "..."
        ctk.CTkLabel(card, text=name, font=FONT_MONO_SM, text_color=APP_TEXT_MUTED).pack(pady=(0, 6))

        def on_click(_e=None, p=path, c=card):
            self._select_card(p, c)

        def on_dbl(_e=None, p=path):
            self._select_card(path, card)
            self.open_lightbox()

        card.bind("<Button-1>", on_click)
        card.bind("<Double-Button-1>", on_dbl)
        card.bind("<Button-3>", lambda e, p=path: self._show_card_context_menu(e, p))

        def on_enter(_e=None, c=card, p=path):
            if self._selected != p:
                c.configure(border_color=APP_ACCENT)

        def on_leave(_e=None, c=card, p=path):
            c.configure(border_color=APP_ACCENT if self._selected == p else APP_BORDER)

        card.bind("<Enter>", on_enter)
        card.bind("<Leave>", on_leave)

        for child in card.winfo_children():
            child.bind("<Button-1>", on_click)
            child.bind("<Double-Button-1>", on_dbl)
            for sub in child.winfo_children():
                sub.bind("<Button-1>", on_click)
                sub.bind("<Double-Button-1>", on_dbl)
        card._filepath = path
        self._thumb_cards[path] = card

    def _show_card_context_menu(self, event, path: str):
        import tkinter as tk
        from app_settings import load_app_settings
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Generate Tags", command=lambda: self._ai_generate_tags(path))
        menu.add_command(label="Generate Caption", command=lambda: self._ai_generate_caption(path))
        menu.add_command(label="Find Similar", command=lambda: self._ai_find_similar(path))
        if not load_app_settings().enable_local_ai:
            menu.entryconfigure(0, state="disabled")
            menu.entryconfigure(1, state="disabled")
            menu.entryconfigure(2, state="disabled")
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _ai_generate_tags(self, path: str):
        from ai_local import generate_tags_local, ollama_available
        from ocr_index import save_ai_metadata, get_ai_caption
        if not ollama_available():
            messagebox.showinfo("Local AI", "Enable Ollama in Settings and ensure it is running.")
            return
        self._notify_status("Generating AI tags…")

        def worker():
            tags = generate_tags_local(path)
            self.after(0, lambda: self._apply_ai_tags(path, tags))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_ai_tags(self, path: str, tags: list[str]):
        from ocr_index import save_ai_metadata, get_ai_caption
        if not tags:
            self._notify_toast("No tags generated")
            return
        save_ai_metadata(path, tags, get_ai_caption(path))
        self._notify_toast(f"AI tags: {', '.join(tags[:6])}")

    def _ai_generate_caption(self, path: str):
        from ai_local import describe_image_local, ollama_available
        if not ollama_available():
            messagebox.showinfo("Local AI", "Enable Ollama in Settings and ensure it is running.")
            return
        self._notify_status("Generating AI caption…")

        def worker():
            caption = describe_image_local(path)
            self.after(0, lambda: self._apply_ai_caption(path, caption))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_ai_caption(self, path: str, caption: str | None):
        from ocr_index import save_ai_metadata, get_ai_tags
        if not caption:
            self._notify_toast("No caption generated")
            return
        save_ai_metadata(path, get_ai_tags(path), caption)
        if self._selected == path:
            self.caption_var.set(caption)
        self._notify_toast("AI caption saved")

    def _ai_find_similar(self, path: str):
        from ai_local import find_similar_local, ollama_available
        if not ollama_available():
            messagebox.showinfo("Local AI", "Enable Ollama in Settings and ensure it is running.")
            return
        similar = find_similar_local(path, self._all_files)
        if not similar:
            messagebox.showinfo("Find Similar", "No similar images found (generate tags first).")
            return
        self._files = similar
        self._render_gallery()
        self._notify_toast(f"Showing {len(similar)} similar image(s)")

    def _select_card(self, path: str, card: ctk.CTkFrame):
        self._selected = path
        for w in self.gallery_grid.winfo_children():
            if isinstance(w, ctk.CTkFrame):
                w.configure(border_color=APP_ACCENT if getattr(w, "_filepath", None) == path else APP_BORDER)
        self._show_selection(path)

    def _show_selection(self, path: str):
        meta = self._read_meta(path)
        self.file_label.configure(text=os.path.basename(path))
        self.embedded_viewer.show_image(path, meta)
        self._fill_form(meta)
        if meta.latitude is not None and meta.longitude is not None:
            self.gps_label.configure(
                text=f"GPS: {meta.latitude:.5f}, {meta.longitude:.5f}",
            )
            self.gps_map_btn.pack(side="right")
        else:
            self.gps_label.configure(text="No GPS in EXIF")
            self.gps_map_btn.pack_forget()

    def redetect_metadata(self):
        if not self._selected:
            messagebox.showinfo("Detect", "Select an image first.")
            return
        self._show_selection(self._selected)

    def _fill_form(self, meta: ImageMetadata):
        self._filling_form = True
        try:
            if meta.date_taken:
                self.date_var.set(meta.date_taken.strftime("%Y-%m-%d %H:%M"))
            else:
                self.date_var.set("")
            self.event_meta_var.set(meta.event)
            self.caption_var.set(meta.caption)
            kw = display_tags(meta.keywords)
            self.keywords_var.set(", ".join(kw))
            self.star_widget.set_rating(meta.rating, notify=False)
            if meta.event:
                self.event_var.set(meta.event)
        finally:
            self._filling_form = False

        summary = format_detection_summary(meta)
        if meta.camera:
            summary += f"\nCamera: {meta.camera}"
        sidecar = find_sidecar(meta.filepath)
        if sidecar:
            summary += f"\n\nSidecar: {os.path.basename(sidecar)}\n{sidecar_preview(sidecar, self._sidecar_mapping)}"
        self.detect_label.configure(text=summary)
        if self.auto_save_var.get():
            self._set_save_status("Edits save automatically")

    def _on_star_click(self, rating: int):
        if not self._selected:
            return
        self._persist_rating(self._selected, rating, show_message=False)

    def _persist_rating(self, path: str, rating: int, show_message: bool = True):
        if not path:
            return
        meta = self._meta_cache.get(path) or self._read_meta(path, blocking=True)
        if meta.rating == rating:
            self.star_widget.set_rating(rating, notify=False)
            return
        ok, msg = write_metadata(path, rating=rating)
        if ok:
            meta.rating = rating
            self._meta_cache[path] = meta
            self.star_widget.set_rating(rating, notify=False)
            self.embedded_viewer.show_image(path, meta)
            self._set_save_status("Saved", saved=True)
            self._notify_toast("Saved")
            self._notify_status("Metadata saved", clear_after_ms=2500)
            if show_message:
                messagebox.showinfo("Rating", f"Saved {rating} star(s).")
        elif show_message:
            messagebox.showerror("Rating", msg)
        else:
            self.star_widget.set_rating(meta.rating, notify=False)

    def _parse_date_entry(self) -> Optional[datetime.datetime]:
        text = self.date_var.get().strip()
        if not text:
            return None
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d %H:%M", "%Y/%m/%d"):
            try:
                return datetime.datetime.strptime(text, fmt)
            except ValueError:
                continue
        raise ValueError("Use date format YYYY-MM-DD HH:MM")

    def save_metadata(self, path: Optional[str] = None, silent: bool = False) -> bool:
        target = path or self._selected
        if not target:
            if not silent:
                messagebox.showinfo("Metadata", "Select an image first.")
            return False
        try:
            dt = self._parse_date_entry()
        except ValueError as e:
            if not silent:
                messagebox.showerror("Date", str(e))
            else:
                self._set_save_status(str(e), error=True)
            return False
        keywords = [k.strip() for k in self.keywords_var.get().split(",") if k.strip()]
        rating = self.star_widget.get_rating()
        ok, msg = write_metadata(
            target,
            date_taken=dt,
            caption=self.caption_var.get().strip(),
            keywords=keywords,
            event=self.event_meta_var.get().strip(),
            rating=rating,
        )
        if ok:
            self._meta_cache[target] = self._read_meta(target, blocking=True)
            if silent:
                self._set_save_status("Saved", saved=True)
                self._notify_toast("Saved")
                self._notify_status("Metadata saved", clear_after_ms=2500)
            else:
                messagebox.showinfo("Metadata", msg)
                self._set_save_status("Saved", saved=True)
                self._notify_toast("Saved")
                self._notify_status("Metadata saved", clear_after_ms=2500)
        elif not silent:
            messagebox.showerror("Metadata", msg)
        else:
            self._set_save_status(msg, error=True)
        return ok

    def select_previous(self):
        if not self._files or not self._selected:
            return
        idx = self._files.index(self._selected)
        self._select_by_index((idx - 1) % len(self._files))

    def select_next(self):
        if not self._files or not self._selected:
            return
        idx = self._files.index(self._selected)
        self._select_by_index((idx + 1) % len(self._files))

    def _select_by_index(self, idx: int):
        if not self._files:
            return
        path = self._files[idx]
        for w in self.gallery_grid.winfo_children():
            if getattr(w, "_filepath", None) == path:
                self._select_card(path, w)
                return
        self._selected = path
        self._show_selection(path)

    def open_lightbox(self):
        if not self._files:
            return
        idx = self._files.index(self._selected) if self._selected in self._files else 0
        if self._lightbox and self._lightbox.winfo_exists():
            self._lightbox.destroy()
        root = self.winfo_toplevel()
        sm = self._shortcut_manager or getattr(root, "shortcut_manager", None)
        self._lightbox = LightboxViewer(
            self.winfo_toplevel(),
            files=list(self._files),
            start_index=idx,
            meta_cache=self._meta_cache,
            on_rating_change=self._lightbox_rating,
            on_save=lambda p: self.save_metadata(p, silent=True),
            shortcut_manager=sm,
            metadata_provider=self._metadata,
        )

    def _lightbox_rating(self, path: str, rating: int):
        self._persist_rating(path, rating, show_message=False)
        if self._selected == path:
            self.star_widget.set_rating(rating, notify=False)

    def open_sidecar_merge_dialog(self, preselect_path: Optional[str] = None):
        folder = self.folder_var.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showerror("Sidecar merge", "Load a folder first.")
            return
        pairs = find_sidecar_pairs(folder, recursive=self.recursive_var.get())
        if not pairs:
            messagebox.showinfo("Sidecar merge", "No image + sidecar pairs found in this folder.")
            return

        def on_done():
            self._reload_sidecar_mapping()
            if self._selected:
                self._show_selection(self._selected)
            self.load_folder()
            self._notify_status("Sidecar merge complete", clear_after_ms=4000)

        def on_mapping():
            SidecarMappingDialog(self.winfo_toplevel(), on_saved=self._reload_sidecar_mapping)

        dialog = SidecarMergeDialog(
            self.winfo_toplevel(),
            pairs=pairs,
            mapping=self._sidecar_mapping,
            delete_sidecar=self.delete_sidecar_var.get(),
            on_done=on_done,
            on_toast=self._notify_toast,
            on_mapping=on_mapping,
        )
        if preselect_path:
            for var, (image_path, _) in dialog._checks:
                var.set(image_path == preselect_path)

    def merge_selected_sidecar(self):
        if not self._selected:
            messagebox.showinfo("Sidecar merge", "Select an image that has a matching sidecar first.")
            return
        sidecar = find_sidecar(self._selected)
        if not sidecar:
            messagebox.showinfo(
                "Sidecar merge",
                f"No sidecar found for {os.path.basename(self._selected)}.\n\n"
                "Expected photo.json, photo.metadata.json, or photo.xmp next to the image.",
            )
            return
        delete = self.delete_sidecar_var.get()
        if delete and not messagebox.askyesno(
            "Delete sidecar?",
            f"Merge metadata into the image and delete {os.path.basename(sidecar)}?",
        ):
            return
        ok, msg = merge_sidecar_into_image(
            self._selected, sidecar, delete_sidecar=delete, mapping=self._sidecar_mapping,
        )
        if ok:
            self._notify_toast("Sidecar merged")
            self._notify_status(msg, clear_after_ms=4000)
            self._show_selection(self._selected)
            self.load_folder()
        else:
            messagebox.showerror("Sidecar merge", msg)

    def merge_all_sidecars_ui(self):
        """Open review dialog (legacy alias)."""
        self.open_sidecar_merge_dialog()

    def preview_rename(self):
        folder = self.folder_var.get().strip()
        event = self.event_var.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showerror("Error", "Load a folder first.")
            return
        if not event:
            messagebox.showerror("Error", "Enter an event name for the rename pattern.")
            return
        self._rename_plan = bulk_rename_plan(
            folder, event, use_exif_date=self.exif_date_var.get(), recursive=self.recursive_var.get(),
        )
        text = format_rename_preview(self._rename_plan)
        self.rename_preview.configure(state="normal")
        self.rename_preview.delete("1.0", "end")
        self.rename_preview.insert("1.0", text)
        self.rename_preview.configure(state="disabled")

    def apply_rename(self):
        if not self._rename_plan:
            self.preview_rename()
            if not self._rename_plan:
                return
        if not messagebox.askyesno("Confirm", f"Rename {len(self._rename_plan)} file(s)?"):
            return
        done, errors = apply_rename_plan(self._rename_plan)
        msg = f"Renamed {done} file(s)."
        if errors:
            msg += "\n\n" + "\n".join(errors[:6])
        messagebox.showinfo("Bulk rename", msg)
        self.load_folder()

    def _export_metas(self) -> list[ImageMetadata]:
        metas = []
        for path in self._files:
            meta = self._meta_cache.get(path) or self._read_meta(path, blocking=True)
            self._meta_cache[path] = meta
            metas.append(meta)
        return metas

    def export_csv(self):
        if not self._files:
            messagebox.showinfo("Export", "No files to export. Load and filter a folder first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV", "*.csv")], title="Export metadata as CSV",
        )
        if not path:
            return
        try:
            n = export_metadata_csv(self._export_metas(), path)
            messagebox.showinfo("Export", f"Exported {n} record(s) to CSV.")
        except OSError as exc:
            messagebox.showerror("Export", str(exc))

    def export_json(self):
        if not self._files:
            messagebox.showinfo("Export", "No files to export. Load and filter a folder first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=[("JSON", "*.json")], title="Export metadata as JSON",
        )
        if not path:
            return
        try:
            n = export_metadata_json(self._export_metas(), path)
            messagebox.showinfo("Export", f"Exported {n} record(s) to JSON.")
        except OSError as exc:
            messagebox.showerror("Export", str(exc))

    def _playlist_names(self) -> list[str]:
        return ["(no playlist)"] + [p.name for p in self._playlist_store.playlists]

    def _refresh_playlist_menu(self):
        if hasattr(self, "playlist_menu"):
            self.playlist_menu.configure(values=self._playlist_names())

    def _save_playlist(self):
        from tkinter import simpledialog
        name = simpledialog.askstring("Save playlist", "Name for current filters:")
        if not name or not name.strip():
            return
        tag = self.tag_filter_var.get()
        pl = SmartPlaylist(
            name=name.strip(),
            min_rating=int(self.min_rating_var.get().replace("+", "") or 0),
            tag="" if tag in ("", "(all tags)") else tag,
            search=self.search_var.get().strip(),
            match_all_tags=self.match_all_var.get(),
            gallery_sort=self.sort_var.get(),
            date_from=self.date_from_var.get().strip(),
            date_to=self.date_to_var.get().strip(),
        )
        self._playlist_store.playlists = [p for p in self._playlist_store.playlists if p.name != pl.name]
        self._playlist_store.playlists.append(pl)
        self._playlist_store.save()
        self._refresh_playlist_menu()
        self.playlist_var.set(pl.name)
        self._notify_toast(f"Saved playlist '{pl.name}'")

    def _on_playlist_selected(self, name: str):
        if name == "(no playlist)":
            return
        pl = next((p for p in self._playlist_store.playlists if p.name == name), None)
        if not pl:
            return
        self.tag_filter_var.set(pl.tag if pl.tag else "(all tags)")
        self.min_rating_var.set(f"{pl.min_rating}+")
        self.search_var.set(pl.search)
        self.match_all_var.set(pl.match_all_tags)
        if pl.gallery_sort:
            self.sort_var.set(pl.gallery_sort)
        self.date_from_var.set(pl.date_from or "")
        self.date_to_var.set(pl.date_to or "")
        self.apply_filters()

    def open_side_by_side_compare(self):
        if not self._selected:
            messagebox.showinfo("Compare", "Select a photo first.")
            return
        anchor = self._compare_anchor or self._selected
        other = self._selected if anchor != self._selected else None
        if other is None:
            path = filedialog.askopenfilename(
                title="Compare with…",
                filetypes=[("Images", "*.jpg *.jpeg *.png *.webp *.heic"), ("All", "*.*")],
            )
            if not path:
                return
            other = path
        SideBySideCompareDialog(self, anchor, other)
        self._compare_anchor = self._selected

    def find_similar_images(self):
        if not HAS_IMAGEHASH:
            messagebox.showinfo("Find similar", "Install imagehash: pip install imagehash")
            return
        if not self._selected:
            messagebox.showinfo("Find similar", "Select a photo first.")
            return
        target = self._selected
        target_hash = self._phash_cache.get(target)
        if not target_hash:
            target_hash = calculate_perceptual_hash(target)
            if target_hash:
                self._phash_cache[target] = target_hash
        if not target_hash:
            messagebox.showerror("Find similar", "Could not compute perceptual hash.")
            return
        tol = load_app_settings().phash_tolerance
        library: list[tuple[str, str]] = []
        for path in self._all_files:
            if path == target:
                continue
            ext = os.path.splitext(path)[1].lower()
            if ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff", ".heic"}:
                continue
            h = self._phash_cache.get(path)
            if not h:
                h = calculate_perceptual_hash(path)
                if h:
                    self._phash_cache[path] = h
            if h:
                library.append((path, h))
        matches = find_similar_paths(target_hash, library, tol, limit=64)
        if not matches:
            messagebox.showinfo("Find similar", f"No similar images within tolerance {tol}.")
            return
        self._files = [p for p, _ in matches]
        self._render_gallery(self._files)
        self.count_label.configure(text=f"{len(matches)} similar to {os.path.basename(target)}")

    def import_takeout_albums(self):
        folder = filedialog.askdirectory(title="Select Google Takeout extract folder")
        if not folder:
            return
        albums = discover_takeout_albums(folder)
        if not albums:
            messagebox.showinfo("Takeout albums", "No album folders found in this Takeout extract.")
            return
        names = [f"{a['name']} ({a['image_count']} imgs)" for a in albums[:20]]
        from tkinter import simpledialog
        choice = simpledialog.askstring(
            "Takeout albums",
            "Albums found:\n" + "\n".join(names) + "\n\nEnter exact album name to import:",
        )
        if not choice:
            return
        album = next((a for a in albums if a["name"].lower() == choice.strip().lower()), None)
        if not album:
            messagebox.showerror("Takeout albums", f"Album '{choice}' not found.")
            return
        found, merged, errors = import_takeout_album(album["path"])
        summary = f"Album '{album['name']}': {found} sidecar(s), merged {merged}."
        if errors:
            summary += "\n\n" + "\n".join(errors[:6])
        messagebox.showinfo("Takeout albums", summary)
        self.folder_var.set(album["path"])
        self.load_folder()

    def _open_selected_on_map(self):
        if not self._selected:
            return
        meta = self._meta_cache.get(self._selected) or self._read_meta(self._selected)
        if meta.latitude is not None and meta.longitude is not None:
            open_in_browser(meta.latitude, meta.longitude)

    def open_map_view(self):
        if not self._all_files:
            messagebox.showinfo("Map", "Load a folder first.")
            return
        GpsMapDialog(self, self._all_files, self._meta_cache)

    def merge_takeout_folder(self):
        folder = self.folder_var.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showerror("Takeout", "Load a folder first.")
            return
        paths = list_images(folder, recursive=self.recursive_var.get())
        merged = 0
        found = 0
        errors = []
        for path in paths:
            sidecar = find_takeout_sidecar(path)
            if not sidecar:
                continue
            found += 1
            ok, msg = merge_sidecar_into_image(path, sidecar, delete_sidecar=False)
            if ok:
                merged += 1
            else:
                errors.append(f"{os.path.basename(path)}: {msg}")
        summary = f"Found {found} Takeout sidecar(s), merged {merged}."
        if errors:
            summary += "\n\n" + "\n".join(errors[:6])
        messagebox.showinfo("Google Takeout", summary)
        self.load_folder()

    def open_autodetect_wizard(self):
        folder = self.folder_var.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showerror("Autodetect", "Load a folder first.")
            return
        paths = self._files if self._files else list_images(folder, recursive=self.recursive_var.get())
        AutodetectWizardDialog(self, paths, on_done=self.load_folder)


class AutodetectWizardDialog(ctk.CTkToplevel):
    """Batch metadata imputation from filenames, folders, and file dates."""

    def __init__(self, parent, paths: list[str], on_done: Optional[Callable[[], None]] = None):
        super().__init__(parent)
        self.title("Metadata autodetect wizard")
        self.geometry("640x480")
        self.transient(parent)
        self.grab_set()
        self.configure(fg_color=WINDOW_BG)
        self._on_done = on_done
        self._plan = batch_autodetect_plan(paths)

        ctk.CTkLabel(
            self, text="Metadata autodetect wizard",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(14, 4))
        ctk.CTkLabel(
            self,
            text=f"Found {len(self._plan)} file(s) with metadata that can be inferred from paths or filenames.",
            font=ctk.CTkFont(size=12), text_color=APP_TEXT_MUTED, wraplength=580, justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 8))

        box = ctk.CTkTextbox(self, wrap="word", font=("Consolas", 10))
        box.pack(fill="both", expand=True, padx=16, pady=8)
        lines = []
        for path, meta, fields in self._plan[:80]:
            lines.append(f"{os.path.basename(path)}")
            lines.append(f"  fields: {', '.join(fields)} — {format_detection_summary(meta)}")
        if len(self._plan) > 80:
            lines.append(f"... and {len(self._plan) - 80} more")
        box.insert("1.0", "\n".join(lines) if lines else "No missing metadata detected.")
        box.configure(state="disabled")

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 14))
        SecondaryButton(row, text="Cancel", width=100, command=self.destroy).pack(side="right")
        PrimaryButton(
            row, text=f"Apply to {len(self._plan)} file(s)", width=160, command=self._apply_all,
        ).pack(side="right", padx=(0, 8))

    def _apply_all(self):
        if not self._plan:
            self.destroy()
            return
        if not messagebox.askyesno("Confirm", f"Write inferred metadata to {len(self._plan)} file(s)?"):
            return
        ok_count = 0
        errors = []
        for path, meta, fields in self._plan:
            ok, msg = apply_autodetected_metadata(path, meta, fields)
            if ok:
                ok_count += 1
            else:
                errors.append(f"{os.path.basename(path)}: {msg}")
        summary = f"Updated {ok_count} of {len(self._plan)} file(s)."
        if errors:
            summary += "\n\n" + "\n".join(errors[:8])
        messagebox.showinfo("Autodetect", summary)
        self.destroy()
        if self._on_done:
            self._on_done()


class GpsMapDialog(ctk.CTkToplevel):
    """List geotagged photos and open locations in OpenStreetMap."""

    def __init__(self, parent, paths: list[str], meta_cache: dict[str, ImageMetadata]):
        super().__init__(parent)
        self.title("GPS map — geotagged photos")
        self.geometry("620x460")
        self.transient(parent)
        self.grab_set()
        self.configure(fg_color=WINDOW_BG)

        geotagged: list[tuple[str, float, float]] = []
        for path in paths:
            meta = meta_cache.get(path) or self._read_meta(path)
            meta_cache[path] = meta
            if meta.latitude is not None and meta.longitude is not None:
                geotagged.append((path, meta.latitude, meta.longitude))

        ctk.CTkLabel(
            self, text=f"{len(geotagged)} geotagged photo(s) in folder",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(14, 8))

        box = ctk.CTkTextbox(self, wrap="none", font=("Consolas", 10))
        box.pack(fill="both", expand=True, padx=16, pady=8)
        for path, lat, lon in geotagged[:500]:
            box.insert("end", f"{os.path.basename(path)}\n  {lat:.5f}, {lon:.5f}\n  {osm_url(lat, lon)}\n\n")
        if len(geotagged) > 500:
            box.insert("end", f"... and {len(geotagged) - 500} more\n")
        box.configure(state="disabled")

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 14))
        SecondaryButton(row, text="Close", width=100, command=self.destroy).pack(side="right")
        if geotagged:
            first = geotagged[0]
            PrimaryButton(
                row, text="Open first in browser", width=150,
                command=lambda: open_in_browser(first[1], first[2]),
            ).pack(side="right", padx=(0, 8))
