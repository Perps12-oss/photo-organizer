"""
Central Settings page — appearance, gallery, sidecar, watcher defaults, shortcuts.
"""
from __future__ import annotations

from tkinter import messagebox
from typing import Callable, Optional

import customtkinter as ctk

from tkinter import filedialog

import os

from app_settings import (
    AppSettings, SCAN_DEPTH_OPTIONS, SETTINGS_DIR, load_app_settings, save_app_settings,
)
from inbox_watcher import WatcherSettings, load_settings, save_settings, is_windows_autostart_enabled, set_windows_autostart
from design_system import ModernSlider, PageHeader, PrimaryButton, SecondaryButton, StyledCheckBox, StyledOptionMenu
from theme import (
    APPEARANCE_MODES, APP_BORDER, APP_TEXT_MUTED, BODY_FONT, CONTENT_MARGIN, GALLERY_SORT_OPTIONS,
    INPUT_BG, PAD_MD, SECTION_GAP, TEXT_SECONDARY,
)
from keyboard_bindings import ACTION_LABELS, DEFAULT_BINDINGS, shortcuts_reference_text
from ui_components import SettingsSection


class SettingsView(ctk.CTkFrame):
    """Unified preferences UI."""

    def __init__(
        self,
        parent,
        on_theme_change: Optional[Callable[[str], None]] = None,
        on_gallery_settings_saved: Optional[Callable[[], None]] = None,
        on_open_sidecar_mapping: Optional[Callable[[], None]] = None,
        on_open_inbox: Optional[Callable[[], None]] = None,
        on_toast: Optional[Callable[[str], None]] = None,
        on_idle_scan_saved: Optional[Callable[[], None]] = None,
        shortcut_manager=None,
    ):
        super().__init__(parent, fg_color="transparent")
        self._on_theme_change = on_theme_change
        self._on_gallery_settings_saved = on_gallery_settings_saved
        self._on_open_sidecar_mapping = on_open_sidecar_mapping
        self._on_open_inbox = on_open_inbox
        self._on_toast = on_toast
        self._on_idle_scan_saved = on_idle_scan_saved
        self._shortcut_manager = shortcut_manager
        self._shortcut_vars: dict[str, ctk.StringVar] = {}
        self._capturing_action: str | None = None

        self._app = load_app_settings()
        self._watcher = load_settings()

        self.appearance_var = ctk.StringVar(value=self._app.appearance_mode)
        self.auto_save_var = ctk.BooleanVar(value=self._app.auto_save_metadata)
        self.auto_save_delay_var = ctk.DoubleVar(value=self._app.auto_save_delay_ms)
        self.gallery_sort_var = ctk.StringVar(value=self._app.gallery_sort)
        self.metadata_collapsed_var = ctk.BooleanVar(value=self._app.metadata_panel_collapsed)

        self.watcher_poll_var = ctk.DoubleVar(value=self._watcher.poll_seconds)
        self.watcher_start_launch_var = ctk.BooleanVar(value=self._watcher.start_on_launch)
        self.watcher_tray_var = ctk.BooleanVar(value=self._watcher.minimize_to_tray)
        self.watcher_recursive_var = ctk.BooleanVar(value=self._watcher.recursive)
        self.watcher_login_var = ctk.BooleanVar(value=is_windows_autostart_enabled())

        self.idle_scan_var = ctk.BooleanVar(value=self._app.idle_duplicate_scan_enabled)
        self.idle_scan_folder_var = ctk.StringVar(value=self._app.idle_duplicate_scan_folder)
        self.idle_scan_days_var = ctk.DoubleVar(value=float(self._app.idle_duplicate_scan_days))
        self.idle_idle_min_var = ctk.DoubleVar(value=float(self._app.idle_duplicate_scan_idle_minutes))
        self.idle_cooldown_var = ctk.DoubleVar(value=float(self._app.idle_duplicate_scan_cooldown_hours))
        self.idle_cpu_limit_var = ctk.DoubleVar(value=float(self._app.idle_duplicate_scan_cpu_limit))
        self.idle_skip_battery_var = ctk.BooleanVar(value=self._app.idle_duplicate_scan_skip_on_battery)
        self.idle_locked_only_var = ctk.BooleanVar(value=self._app.idle_duplicate_scan_only_when_locked)
        self.locale_var = ctk.StringVar(value=self._app.locale)
        self.default_scan_depth_var = ctk.StringVar(value=self._app.scan_depth_label)
        self.enable_local_ai_var = ctk.BooleanVar(value=self._app.enable_local_ai)
        self.ollama_url_var = ctk.StringVar(value=self._app.ollama_url)
        self.snapshot_before_delete_var = ctk.BooleanVar(value=self._app.snapshot_before_delete)
        self.use_media_index_var = ctk.BooleanVar(value=self._app.use_media_index)
        self.auto_ocr_var = ctk.BooleanVar(value=self._app.auto_ocr_on_folder_load)
        self.custom_accent_var = ctk.StringVar(value=self._app.custom_accent or "")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        PageHeader(
            self, "Settings", "Appearance, gallery behavior, sidecar mapping, and inbox watcher defaults.",
        ).grid(row=0, column=0, sticky="ew", padx=CONTENT_MARGIN, pady=(CONTENT_MARGIN, SECTION_GAP))

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.grid(row=1, column=0, sticky="nsew", padx=CONTENT_MARGIN, pady=(0, 8))
        scroll.grid_columnconfigure(0, weight=1)

        self._build_appearance_section(scroll)
        self._build_gallery_section(scroll)
        self._build_sidecar_section(scroll)
        self._build_watcher_section(scroll)
        self._build_duplicate_scan_section(scroll)
        self._build_safety_section(scroll)
        self._build_ai_section(scroll)
        self._build_shortcuts_section(scroll)

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=CONTENT_MARGIN, pady=(8, CONTENT_MARGIN))
        PrimaryButton(footer, text="Save all settings", width=160, command=self.save_all).pack(side="left")
        SecondaryButton(footer, text="Reset to defaults", width=140, command=self.reset_defaults).pack(
            side="left", padx=(12, 0),
        )
        SecondaryButton(footer, text="Open config folder", width=150, command=self._open_config_folder).pack(
            side="left", padx=(12, 0),
        )

    def _build_appearance_section(self, parent):
        section = SettingsSection(
            parent, "Appearance",
            "Theme for the app shell and gallery. Saved automatically when you change it.",
        )
        section.pack(fill="x", pady=(0, PAD_MD))
        row = ctk.CTkFrame(section.body, fg_color="transparent")
        row.pack(fill="x", pady=4)
        ctk.CTkLabel(row, text="Theme", width=140, anchor="w").pack(side="left")
        StyledOptionMenu(
            row, variable=self.appearance_var, values=list(APPEARANCE_MODES),
            width=200, command=self._on_theme_selected,
        ).pack(side="left")
        row2 = ctk.CTkFrame(section.body, fg_color="transparent")
        row2.pack(fill="x", pady=4)
        ctk.CTkLabel(row2, text="Accent color", width=140, anchor="w").pack(side="left")
        ctk.CTkEntry(
            row2, textvariable=self.custom_accent_var, placeholder_text="#00ffcc (optional)", width=200,
        ).pack(side="left")
        row3 = ctk.CTkFrame(section.body, fg_color="transparent")
        row3.pack(fill="x", pady=4)
        ctk.CTkLabel(row3, text="Language", width=140, anchor="w").pack(side="left")
        StyledOptionMenu(
            row3, variable=self.locale_var, values=["en", "de", "fr", "es"], width=120,
        ).pack(side="left")

    def _build_gallery_section(self, parent):
        section = SettingsSection(
            parent, "Media Gallery",
            "Default behavior when browsing photos and editing metadata.",
        )
        section.pack(fill="x", pady=(0, PAD_MD))

        row1 = ctk.CTkFrame(section.body, fg_color="transparent")
        row1.pack(fill="x", pady=4)
        StyledCheckBox(
            row1, text="Auto-save metadata edits", variable=self.auto_save_var,
        ).pack(side="left")

        row2 = ctk.CTkFrame(section.body, fg_color="transparent")
        row2.pack(fill="x", pady=4)
        ctk.CTkLabel(row2, text="Auto-save delay", width=140, anchor="w").pack(side="left")
        ModernSlider(
            row2, from_=300, to=2000, number_of_steps=17,
            variable=self.auto_save_delay_var, width=220,
            command=self._update_delay_label,
        ).pack(side="left", padx=(0, 8))
        self._delay_label = ctk.CTkLabel(row2, text=f"{int(self.auto_save_delay_var.get())} ms", width=70, anchor="w")
        self._delay_label.pack(side="left")

        row3 = ctk.CTkFrame(section.body, fg_color="transparent")
        row3.pack(fill="x", pady=4)
        ctk.CTkLabel(row3, text="Default sort", width=140, anchor="w").pack(side="left")
        StyledOptionMenu(
            row3, variable=self.gallery_sort_var, values=list(GALLERY_SORT_OPTIONS), width=200,
        ).pack(side="left")

        row4 = ctk.CTkFrame(section.body, fg_color="transparent")
        row4.pack(fill="x", pady=4)
        StyledCheckBox(
            row4, text="Start with metadata panel collapsed", variable=self.metadata_collapsed_var,
        ).pack(side="left")

        row5 = ctk.CTkFrame(section.body, fg_color="transparent")
        row5.pack(fill="x", pady=4)
        StyledCheckBox(
            row5, text="Auto-build OCR search index when a folder loads",
            variable=self.auto_ocr_var,
        ).pack(side="left")

    def _build_sidecar_section(self, parent):
        section = SettingsSection(
            parent, "Sidecar merge",
            "Map JSON/XMP sidecar keys to EXIF fields before merging into images.",
        )
        section.pack(fill="x", pady=(0, PAD_MD))
        row = ctk.CTkFrame(section.body, fg_color="transparent")
        row.pack(fill="x", pady=4)
        ctk.CTkButton(
            row, text="Edit field mapping…", width=160,
            fg_color="transparent", border_width=1, border_color=APP_BORDER,
            command=self._open_mapping,
        ).pack(side="left")

    def _build_watcher_section(self, parent):
        section = SettingsSection(
            parent, "Inbox Watcher defaults",
            "Background routing preferences. Paths and rules are configured on the Inbox Watcher tab.",
        )
        section.pack(fill="x", pady=(0, PAD_MD))

        row1 = ctk.CTkFrame(section.body, fg_color="transparent")
        row1.pack(fill="x", pady=4)
        ctk.CTkLabel(row1, text="Poll interval", width=140, anchor="w").pack(side="left")
        ModernSlider(
            row1, from_=1, to=10, number_of_steps=9,
            variable=self.watcher_poll_var, width=220,
            command=self._update_poll_label,
        ).pack(side="left", padx=(0, 8))
        self._poll_label = ctk.CTkLabel(row1, text=f"{self.watcher_poll_var.get():.0f}s", width=50, anchor="w")
        self._poll_label.pack(side="left")

        row2 = ctk.CTkFrame(section.body, fg_color="transparent")
        row2.pack(fill="x", pady=4)
        StyledCheckBox(row2, text="Start watcher on app launch", variable=self.watcher_start_launch_var).pack(
            side="left", padx=(0, 16),
        )
        StyledCheckBox(row2, text="Minimize to system tray on close", variable=self.watcher_tray_var).pack(side="left")

        row3 = ctk.CTkFrame(section.body, fg_color="transparent")
        row3.pack(fill="x", pady=4)
        StyledCheckBox(row3, text="Scan subfolders recursively", variable=self.watcher_recursive_var).pack(
            side="left", padx=(0, 16),
        )
        StyledCheckBox(row3, text="Run at Windows login", variable=self.watcher_login_var).pack(side="left")

        if self._on_open_inbox:
            ctk.CTkButton(
                section.body, text="Open Inbox Watcher →", width=180,
                fg_color="transparent", border_width=1, border_color=APP_BORDER,
                command=self._on_open_inbox,
            ).pack(anchor="w", pady=(8, 0))

    def _build_duplicate_scan_section(self, parent):
        section = SettingsSection(
            parent, "Duplicate Finder",
            "Time-filtered scans and background idle scanning when you're away from the PC.",
        )
        section.pack(fill="x", pady=(0, PAD_MD))

        row0 = ctk.CTkFrame(section.body, fg_color="transparent")
        row0.pack(fill="x", pady=4)
        ctk.CTkLabel(row0, text="Default scan depth", width=140, anchor="w").pack(side="left")
        StyledOptionMenu(
            row0, variable=self.default_scan_depth_var, values=list(SCAN_DEPTH_OPTIONS), width=160,
        ).pack(side="left")

        row1 = ctk.CTkFrame(section.body, fg_color="transparent")
        row1.pack(fill="x", pady=4)
        StyledCheckBox(
            row1,
            text="Scan for duplicates when the PC is idle (no mouse/keyboard, tray, or locked)",
            variable=self.idle_scan_var,
        ).pack(side="left")

        row2 = ctk.CTkFrame(section.body, fg_color="transparent")
        row2.pack(fill="x", pady=4)
        ctk.CTkLabel(row2, text="Idle scan folder", width=140, anchor="w").pack(side="left")
        ctk.CTkEntry(row2, textvariable=self.idle_scan_folder_var, placeholder_text="Library root (default)").pack(
            side="left", fill="x", expand=True, padx=(0, 8),
        )
        ctk.CTkButton(row2, text="Browse", width=80, command=self._browse_idle_folder).pack(side="right")

        row3 = ctk.CTkFrame(section.body, fg_color="transparent")
        row3.pack(fill="x", pady=4)
        ctk.CTkLabel(row3, text="Only files newer than", width=140, anchor="w").pack(side="left")
        ModernSlider(row3, from_=7, to=90, number_of_steps=83, variable=self.idle_scan_days_var, width=180).pack(
            side="left", padx=(0, 8),
        )
        self._idle_days_label = ctk.CTkLabel(row3, text=f"{int(self.idle_scan_days_var.get())} days", width=60, anchor="w")
        self._idle_days_label.pack(side="left")
        self.idle_scan_days_var.trace_add("write", self._update_idle_days_label)

        row4 = ctk.CTkFrame(section.body, fg_color="transparent")
        row4.pack(fill="x", pady=4)
        ctk.CTkLabel(row4, text="Idle after", width=140, anchor="w").pack(side="left")
        ModernSlider(row4, from_=2, to=30, number_of_steps=28, variable=self.idle_idle_min_var, width=180).pack(
            side="left", padx=(0, 8),
        )
        self._idle_min_label = ctk.CTkLabel(row4, text=f"{int(self.idle_idle_min_var.get())} min", width=60, anchor="w")
        self._idle_min_label.pack(side="left")
        self.idle_idle_min_var.trace_add("write", self._update_idle_min_label)

        row5 = ctk.CTkFrame(section.body, fg_color="transparent")
        row5.pack(fill="x", pady=4)
        ctk.CTkLabel(row5, text="Cooldown between scans", width=140, anchor="w").pack(side="left")
        ModernSlider(row5, from_=1, to=24, number_of_steps=23, variable=self.idle_cooldown_var, width=180).pack(
            side="left", padx=(0, 8),
        )
        self._idle_cd_label = ctk.CTkLabel(row5, text=f"{int(self.idle_cooldown_var.get())} h", width=60, anchor="w")
        self._idle_cd_label.pack(side="left")
        self.idle_cooldown_var.trace_add("write", self._update_idle_cd_label)

        row6 = ctk.CTkFrame(section.body, fg_color="transparent")
        row6.pack(fill="x", pady=4)
        ctk.CTkLabel(row6, text="Max CPU usage", width=140, anchor="w").pack(side="left")
        ModernSlider(row6, from_=10, to=100, number_of_steps=9, variable=self.idle_cpu_limit_var, width=180).pack(
            side="left", padx=(0, 8),
        )
        self._idle_cpu_label = ctk.CTkLabel(row6, text=f"{int(self.idle_cpu_limit_var.get())}%", width=60, anchor="w")
        self._idle_cpu_label.pack(side="left")
        self.idle_cpu_limit_var.trace_add("write", self._update_idle_cpu_label)

        row7 = ctk.CTkFrame(section.body, fg_color="transparent")
        row7.pack(fill="x", pady=4)
        StyledCheckBox(
            row7, text="Skip idle scan on battery (when psutil available)",
            variable=self.idle_skip_battery_var,
        ).pack(side="left", padx=(0, 16))
        StyledCheckBox(
            row7, text="Only scan when workstation is locked",
            variable=self.idle_locked_only_var,
        ).pack(side="left")

    def _browse_idle_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.idle_scan_folder_var.set(path)

    def _open_config_folder(self):
        folder = str(SETTINGS_DIR)
        if os.name == "nt":
            os.startfile(folder)  # type: ignore[attr-defined]
        elif self._on_toast:
            self._on_toast(f"Config folder: {folder}")

    def _update_idle_days_label(self, *_):
        self._idle_days_label.configure(text=f"{int(self.idle_scan_days_var.get())} days")

    def _update_idle_min_label(self, *_):
        self._idle_min_label.configure(text=f"{int(self.idle_idle_min_var.get())} min")

    def _update_idle_cd_label(self, *_):
        self._idle_cd_label.configure(text=f"{int(self.idle_cooldown_var.get())} h")

    def _update_idle_cpu_label(self, *_):
        self._idle_cpu_label.configure(text=f"{int(self.idle_cpu_limit_var.get())}%")

    def _build_safety_section(self, parent):
        from snapshots import delete_snapshot, list_snapshots, restore_snapshot
        from media_index import index_stats

        section = SettingsSection(
            parent, "Safety & performance",
            "Undo/redo (Ctrl+Z / Ctrl+Y), snapshots before delete, and SQLite media index for large libraries.",
        )
        section.pack(fill="x", pady=(0, PAD_MD))
        row1 = ctk.CTkFrame(section.body, fg_color="transparent")
        row1.pack(fill="x", pady=4)
        StyledCheckBox(
            row1, text="Create snapshot before duplicate delete", variable=self.snapshot_before_delete_var,
        ).pack(side="left", padx=(0, 16))
        StyledCheckBox(
            row1, text="Use SQLite media index when loading gallery", variable=self.use_media_index_var,
        ).pack(side="left")

        stats = index_stats()
        ctk.CTkLabel(
            section.body,
            text=f"Media index: {stats.get('files', 0):,} files across {stats.get('roots', 0)} root(s)",
            font=ctk.CTkFont(size=11), text_color=APP_TEXT_MUTED,
        ).pack(anchor="w", pady=(4, 8))

        snap_row = ctk.CTkFrame(section.body, fg_color="transparent")
        snap_row.pack(fill="x", pady=4)
        self._snapshot_menu = StyledOptionMenu(
            snap_row, values=["(no snapshots)"], width=320,
        )
        self._snapshot_menu.pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            snap_row, text="Refresh", width=80,
            command=lambda: self._refresh_snapshot_menu(),
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            snap_row, text="Restore", width=80,
            command=self._restore_selected_snapshot,
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            snap_row, text="Delete", width=70,
            fg_color="#3a1a1a", hover_color="#5a2020",
            command=self._delete_selected_snapshot,
        ).pack(side="left", padx=4)
        self._refresh_snapshot_menu()

    def _snapshot_labels(self) -> list[str]:
        from snapshots import list_snapshots
        snaps = list_snapshots()
        if not snaps:
            return ["(no snapshots)"]
        return [
            f"{s.label} — {s.file_count} files ({s.created[:16]}) [{s.id}]"
            for s in snaps
        ]

    def _refresh_snapshot_menu(self):
        labels = self._snapshot_labels()
        self._snapshot_menu.configure(values=labels)
        self._snapshot_menu.set(labels[0])

    def _selected_snapshot_id(self) -> str | None:
        val = self._snapshot_menu.get()
        if val == "(no snapshots)" or "[" not in val:
            return None
        return val.rsplit("[", 1)[-1].rstrip("]")

    def _restore_selected_snapshot(self):
        from snapshots import restore_snapshot
        snap_id = self._selected_snapshot_id()
        if not snap_id:
            messagebox.showinfo("Snapshots", "No snapshot selected.")
            return
        overwrite = messagebox.askyesno(
            "Restore snapshot",
            "Restore files to their original paths?\n\nChoose Yes to overwrite existing files.",
        )
        restored, errors = restore_snapshot(snap_id, overwrite=overwrite)
        msg = f"Restored {restored} file(s)."
        if errors:
            msg += f"\n\n{len(errors)} issue(s):\n" + "\n".join(errors[:6])
        messagebox.showinfo("Restore snapshot", msg)

    def _delete_selected_snapshot(self):
        from snapshots import delete_snapshot
        snap_id = self._selected_snapshot_id()
        if not snap_id:
            return
        if messagebox.askyesno("Delete snapshot", "Remove this snapshot backup permanently?"):
            if delete_snapshot(snap_id):
                self._refresh_snapshot_menu()
                if self._on_toast:
                    self._on_toast("Snapshot deleted")

    def _build_ai_section(self, parent):
        section = SettingsSection(
            parent, "Local AI (future)",
            "Ollama integration for auto-tagging and semantic search. Off by default; local-first.",
        )
        section.pack(fill="x", pady=(0, PAD_MD))
        row1 = ctk.CTkFrame(section.body, fg_color="transparent")
        row1.pack(fill="x", pady=4)
        StyledCheckBox(
            row1, text="Enable local AI (Ollama)", variable=self.enable_local_ai_var,
        ).pack(side="left")
        row2 = ctk.CTkFrame(section.body, fg_color="transparent")
        row2.pack(fill="x", pady=4)
        ctk.CTkLabel(row2, text="Ollama URL", width=140, anchor="w").pack(side="left")
        ctk.CTkEntry(row2, textvariable=self.ollama_url_var, width=280).pack(side="left", fill="x", expand=True)

    def _build_shortcuts_section(self, parent):
        section = SettingsSection(
            parent, "Keyboard shortcuts",
            "Click a binding cell and press a key combination. Save to apply across the app.",
        )
        section.pack(fill="x", pady=(0, PAD_MD))

        header = ctk.CTkFrame(section.body, fg_color="transparent")
        header.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(header, text="Action", width=220, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left")
        ctk.CTkLabel(header, text="Binding", anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left")

        table = ctk.CTkScrollableFrame(section.body, height=220, fg_color=INPUT_BG)
        table.pack(fill="x", pady=4)

        overrides = dict(self._app.keyboard_shortcuts or {})
        for action, label in sorted(ACTION_LABELS.items()):
            row = ctk.CTkFrame(table, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=label, width=220, anchor="w").pack(side="left", padx=(4, 8))
            binding = overrides.get(action) or DEFAULT_BINDINGS.get(action, "")
            var = ctk.StringVar(value=binding)
            self._shortcut_vars[action] = var
            btn = ctk.CTkButton(
                row, textvariable=var, width=180, height=28,
                fg_color="transparent", border_width=1, border_color=APP_BORDER,
                command=lambda a=action: self._capture_shortcut(a),
            )
            btn.pack(side="left")

        ctk.CTkButton(
            section.body, text="Reset shortcuts to defaults", width=180,
            fg_color="transparent", border_width=1, border_color=APP_BORDER,
            command=self._reset_shortcuts,
        ).pack(anchor="w", pady=(6, 4))

        ref = ctk.CTkTextbox(
            section.body, height=120, font=("Consolas", 10), fg_color=INPUT_BG,
            text_color="#aabbcc", wrap="word", activate_scrollbars=True,
        )
        ref.pack(fill="x", pady=4)
        ref.insert("1.0", shortcuts_reference_text())
        ref.configure(state="disabled")

    def _capture_shortcut(self, action: str):
        self._capturing_action = action
        var = self._shortcut_vars.get(action)
        if var:
            var.set("Press a key…")
        top = self.winfo_toplevel()
        top.bind("<KeyPress>", self._on_capture_key, add="+")

    def _on_capture_key(self, event):
        if not self._capturing_action:
            return
        action = self._capturing_action
        self._capturing_action = None
        self.winfo_toplevel().unbind("<KeyPress>")
        binding = self._format_key_event(event)
        var = self._shortcut_vars.get(action)
        if var and binding:
            var.set(binding)

    @staticmethod
    def _format_key_event(event) -> str:
        parts: list[str] = []
        state = getattr(event, "state", 0)
        if state & 0x4:
            parts.append("Control")
        if state & 0x1:
            parts.append("Shift")
        if state & 0x20000:
            parts.append("Alt")
        keysym = event.keysym
        if keysym in ("Escape", "Delete", "Return", "space", "Up", "Down", "Left", "Right"):
            key = keysym
        elif len(keysym) == 1:
            key = keysym.lower()
        elif keysym.startswith("F") and keysym[1:].isdigit():
            key = keysym
        elif keysym.startswith("Key-"):
            key = keysym
        else:
            key = keysym.lower()
        if parts:
            return f"<{'-'.join(parts)}-{key}>"
        if key.startswith("F") and key[1:].isdigit():
            return f"<{key}>"
        if len(key) == 1:
            return f"<Key-{key}>"
        return f"<{key}>"

    def _reset_shortcuts(self):
        for action, var in self._shortcut_vars.items():
            var.set(DEFAULT_BINDINGS.get(action, ""))

    def _update_delay_label(self, _value=None):
        self._delay_label.configure(text=f"{int(self.auto_save_delay_var.get())} ms")

    def _update_poll_label(self, _value=None):
        self._poll_label.configure(text=f"{self.watcher_poll_var.get():.0f}s")

    def _on_theme_selected(self, mode: str):
        if self._on_theme_change:
            self._on_theme_change(mode)

    def _apply_custom_accent(self, accent: str) -> None:
        import theme
        if accent and accent.startswith("#"):
            theme.ACCENT = accent
            theme.APP_ACCENT = accent
            theme.APP_PRIMARY = accent
            theme.ACCENT_HOVER = accent
            theme.APP_ACCENT_HOVER = accent
            theme.APP_PRIMARY_HOVER = accent

    def _open_mapping(self):
        if self._on_open_sidecar_mapping:
            self._on_open_sidecar_mapping()

    def reload(self):
        """Refresh form from disk (e.g. after sidecar mapping dialog)."""
        self._app = load_app_settings()
        self._watcher = load_settings()
        self.appearance_var.set(self._app.appearance_mode)
        self.auto_save_var.set(self._app.auto_save_metadata)
        self.auto_save_delay_var.set(self._app.auto_save_delay_ms)
        self.gallery_sort_var.set(self._app.gallery_sort)
        self.metadata_collapsed_var.set(self._app.metadata_panel_collapsed)
        self.watcher_poll_var.set(self._watcher.poll_seconds)
        self.watcher_start_launch_var.set(self._watcher.start_on_launch)
        self.watcher_tray_var.set(self._watcher.minimize_to_tray)
        self.watcher_recursive_var.set(self._watcher.recursive)
        self.watcher_login_var.set(is_windows_autostart_enabled())
        self.idle_scan_var.set(self._app.idle_duplicate_scan_enabled)
        self.idle_scan_folder_var.set(self._app.idle_duplicate_scan_folder)
        self.idle_scan_days_var.set(float(self._app.idle_duplicate_scan_days))
        self.idle_idle_min_var.set(float(self._app.idle_duplicate_scan_idle_minutes))
        self.idle_cooldown_var.set(float(self._app.idle_duplicate_scan_cooldown_hours))
        self.idle_cpu_limit_var.set(float(self._app.idle_duplicate_scan_cpu_limit))
        self.idle_skip_battery_var.set(self._app.idle_duplicate_scan_skip_on_battery)
        self.idle_locked_only_var.set(self._app.idle_duplicate_scan_only_when_locked)
        self.locale_var.set(self._app.locale)
        self.default_scan_depth_var.set(self._app.scan_depth_label)
        self.enable_local_ai_var.set(self._app.enable_local_ai)
        self.ollama_url_var.set(self._app.ollama_url)
        self.snapshot_before_delete_var.set(self._app.snapshot_before_delete)
        self.use_media_index_var.set(self._app.use_media_index)
        self.auto_ocr_var.set(self._app.auto_ocr_on_folder_load)
        self.custom_accent_var.set(self._app.custom_accent or "")
        self._refresh_snapshot_menu()
        self._update_delay_label()
        self._update_poll_label()
        self._update_idle_days_label()
        self._update_idle_min_label()
        self._update_idle_cd_label()

    def _gather_app_settings(self) -> AppSettings:
        return AppSettings(
            appearance_mode=self.appearance_var.get(),
            auto_save_metadata=self.auto_save_var.get(),
            auto_save_delay_ms=max(300, int(self.auto_save_delay_var.get())),
            sidecar_field_mapping=self._app.sidecar_field_mapping,
            metadata_panel_collapsed=self.metadata_collapsed_var.get(),
            gallery_sort=self.gallery_sort_var.get(),
            scan_depth_label=self.default_scan_depth_var.get(),
            idle_duplicate_scan_enabled=self.idle_scan_var.get(),
            idle_duplicate_scan_folder=self.idle_scan_folder_var.get().strip(),
            idle_duplicate_scan_days=max(1, int(self.idle_scan_days_var.get())),
            idle_duplicate_scan_idle_minutes=max(1, int(self.idle_idle_min_var.get())),
            idle_duplicate_scan_cooldown_hours=max(1, int(self.idle_cooldown_var.get())),
            idle_duplicate_scan_cpu_limit=max(10, min(100, int(self.idle_cpu_limit_var.get()))),
            idle_duplicate_scan_skip_on_battery=self.idle_skip_battery_var.get(),
            idle_duplicate_scan_only_when_locked=self.idle_locked_only_var.get(),
            last_idle_duplicate_scan_at=self._app.last_idle_duplicate_scan_at,
            suppress_config_warnings=self._app.suppress_config_warnings,
            suppress_ffmpeg_warning=self._app.suppress_ffmpeg_warning,
            phash_tolerance=self._app.phash_tolerance,
            video_duplicate_tolerance=self._app.video_duplicate_tolerance,
            recent_scan_folders=list(self._app.recent_scan_folders),
            conflict_policy=self._app.conflict_policy,
            folder_template=self._app.folder_template,
            filename_template=self._app.filename_template,
            ollama_url=self.ollama_url_var.get().strip(),
            enable_local_ai=self.enable_local_ai_var.get(),
            snapshot_before_delete=self.snapshot_before_delete_var.get(),
            use_media_index=self.use_media_index_var.get(),
            auto_ocr_on_folder_load=self.auto_ocr_var.get(),
            custom_accent=self.custom_accent_var.get().strip(),
            keyboard_shortcuts={
                action: var.get().strip()
                for action, var in self._shortcut_vars.items()
                if var.get().strip()
            },
            locale=self.locale_var.get().strip() or "en",
        )

    def _gather_watcher_settings(self) -> WatcherSettings:
        ws = load_settings()
        ws.poll_seconds = float(self.watcher_poll_var.get())
        ws.start_on_launch = self.watcher_start_launch_var.get()
        ws.minimize_to_tray = self.watcher_tray_var.get()
        ws.recursive = self.watcher_recursive_var.get()
        return ws

    def save_all(self):
        self._app = self._gather_app_settings()
        save_app_settings(self._app)
        self._apply_custom_accent(self._app.custom_accent)
        watcher = self._gather_watcher_settings()
        save_settings(watcher)
        set_windows_autostart(self.watcher_login_var.get())
        if self._on_gallery_settings_saved:
            self._on_gallery_settings_saved()
        if self._shortcut_manager:
            self._shortcut_manager.rebind_all()
        if self._on_idle_scan_saved:
            self._on_idle_scan_saved()
        if self._on_toast:
            self._on_toast("Settings saved")
        else:
            messagebox.showinfo("Settings", "Settings saved.")

    def reset_defaults(self):
        if not messagebox.askyesno("Reset settings", "Restore default app and watcher preferences?"):
            return
        current = load_settings()
        default_app = AppSettings()
        default_watcher = WatcherSettings(
            library_root=current.library_root,
            inbox_relative=current.inbox_relative,
        )
        save_app_settings(default_app)
        save_settings(default_watcher)
        set_windows_autostart(False)
        self.reload()
        if self._on_theme_change:
            self._on_theme_change(default_app.appearance_mode)
        if self._on_gallery_settings_saved:
            self._on_gallery_settings_saved()
        if self._on_idle_scan_saved:
            self._on_idle_scan_saved()
        if self._on_toast:
            self._on_toast("Defaults restored")
