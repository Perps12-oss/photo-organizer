"""Inbox watcher configuration view."""
import customtkinter as ctk
import os
from tkinter import filedialog, messagebox

from organizer_engine import LayoutMode, DateSource, FileScope, NameMode
from inbox_watcher import (
    InboxWatcher, WatcherSettings,
    load_settings, save_settings, inbox_path,
    set_windows_autostart, is_windows_autostart_enabled,
)
from design_system import ElevatedCard, ModernSlider, PageHeader, PrimaryButton, SecondaryButton, StyledCheckBox, StyledOptionMenu
from theme import (
    ACCENT, APP_ACCENT, APP_BORDER, APP_CARD, APP_DANGER, APP_DANGER_HOVER, APP_SUCCESS, APP_SUCCESS_HOVER,
    APP_TEXT, APP_TEXT_MUTED, BODY_FONT, BORDER, BTN_ACTIVE, CONTENT_MARGIN, ERROR, FONT_MONO_SM, INPUT_BG,
    INPUT_RADIUS, SECTION_FONT, SECTION_GAP, SIDEBAR_TILE_ACTIVE, SUCCESS, TEXT_PRIMARY, WARNING,
)
from ui_components import INBOX_SHORTCUTS
from views.helpers import truncate_middle
from i18n import t

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from photo_organizer_enhanced import PhotoOrganizerApp

class InboxWatcherView(ctk.CTkFrame):
    """Background monitor for 01_Inbox — routes files using organizer rules."""

    def __init__(self, parent, watcher: InboxWatcher, app: "PhotoOrganizerApp", shortcut_manager=None):
        super().__init__(parent, fg_color="transparent")
        self.watcher = watcher
        self.app = app
        self._shortcut_manager = shortcut_manager
        settings = load_settings()

        self.library_root = ctk.StringVar(value=settings.library_root)
        self.inbox_rel = ctk.StringVar(value=settings.inbox_relative)
        self.layout_var = ctk.StringVar(value=settings.layout)
        self.date_var = ctk.StringVar(value=settings.date_source)
        self.scope_var = ctk.StringVar(value=settings.scope)
        self.name_var = ctk.StringVar(value=settings.name_mode)
        self.action_var = ctk.StringVar(value=settings.action)
        self.poll_var = ctk.DoubleVar(value=settings.poll_seconds)
        self.start_on_launch_var = ctk.BooleanVar(value=settings.start_on_launch)
        self.run_at_login_var = ctk.BooleanVar(value=is_windows_autostart_enabled())
        self.minimize_tray_var = ctk.BooleanVar(value=settings.minimize_to_tray)
        self._pulse_job = None
        self._inbox_key_bindings: list = []

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        PageHeader(self, t("inbox.title"), t("inbox.subtitle")).grid(
            row=0, column=0, sticky="ew", padx=CONTENT_MARGIN, pady=(CONTENT_MARGIN, SECTION_GAP),
        )

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=CONTENT_MARGIN, pady=(0, CONTENT_MARGIN))
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        left_card = ElevatedCard(body)
        left_card.grid(row=0, column=0, padx=(0, 8), sticky="nsew")
        left = left_card.body
        ctk.CTkLabel(left, text="Paths & rules", font=SECTION_FONT).pack(
            anchor="w", pady=(0, 10))

        self._path_row(left, "Library root", self.library_root, self.browse_library)
        self._path_row(left, "Inbox subfolder", self.inbox_rel, None, entry_only=True)

        for label, var, values in (
            ("Folder layout", self.layout_var, [m.value for m in LayoutMode]),
            ("Date from", self.date_var, [d.value for d in DateSource]),
            ("Include files", self.scope_var, [s.value for s in FileScope]),
            ("Rename", self.name_var, [n.value for n in NameMode]),
        ):
            self._option_row(left, label, var, values)

        act = ctk.CTkFrame(left, fg_color="transparent")
        act.pack(fill="x", padx=14, pady=4)
        ctk.CTkLabel(act, text="Action", width=100, anchor="w").pack(side="left")
        ctk.CTkRadioButton(act, text="Move", variable=self.action_var, value="move").pack(side="left", padx=(0, 12))
        ctk.CTkRadioButton(act, text="Copy", variable=self.action_var, value="copy").pack(side="left")

        poll = ctk.CTkFrame(left, fg_color="transparent")
        poll.pack(fill="x", padx=14, pady=(8, 4))
        ctk.CTkLabel(poll, text="Poll every", width=100, anchor="w").pack(side="left")
        ModernSlider(poll, from_=1, to=10, number_of_steps=9, variable=self.poll_var, width=180).pack(side="left", padx=8)
        self.poll_label = ctk.CTkLabel(poll, text=f"{settings.poll_seconds:.0f}s", width=40)
        self.poll_label.pack(side="left")
        self.poll_var.trace_add("write", self._update_poll_label)

        opts = ctk.CTkFrame(left, fg_color="transparent")
        opts.pack(fill="x", padx=14, pady=(8, 14))
        StyledCheckBox(opts, text="Start watcher when app opens", variable=self.start_on_launch_var).pack(anchor="w", pady=2)
        StyledCheckBox(opts, text="Run Photo Organizer at Windows login", variable=self.run_at_login_var).pack(anchor="w", pady=2)
        StyledCheckBox(opts, text="Minimize to tray when closing window", variable=self.minimize_tray_var).pack(anchor="w", pady=2)
        if not TrayController.available():
            ctk.CTkLabel(opts, text="Install pystray for system tray: pip install pystray",
                         text_color=WARNING, font=ctk.CTkFont(size=11)).pack(anchor="w", pady=(4, 0))

        right_card = ElevatedCard(body)
        right_card.grid(row=0, column=1, padx=(8, 0), sticky="nsew")
        right = right_card.body
        right.grid_rowconfigure(3, weight=1)
        right.grid_columnconfigure(0, weight=1)

        self.status_card = ctk.CTkFrame(
            right, fg_color=INPUT_BG, corner_radius=INPUT_RADIUS,
            border_width=1, border_color=BORDER,
        )
        self.status_card.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        card_top = ctk.CTkFrame(self.status_card, fg_color="transparent")
        card_top.pack(fill="x", padx=16, pady=(14, 6))
        ctk.CTkLabel(card_top, text="Watcher status", font=SECTION_FONT,
                     text_color=APP_TEXT_MUTED).pack(side="left")
        self.status_badge = ctk.CTkLabel(
            card_top, text="● STOPPED", text_color=ERROR,
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.status_badge.pack(side="right")

        self.last_file_label = ctk.CTkLabel(
            self.status_card, text="Last file: —",
            font=FONT_MONO_SM, text_color=APP_TEXT, anchor="w", justify="left",
        )
        self.last_file_label.pack(fill="x", padx=16, pady=(0, 4))

        self.last_dest_label = ctk.CTkLabel(
            self.status_card, text="Routed to: —",
            font=FONT_MONO_SM, text_color=APP_TEXT_MUTED, anchor="w", justify="left",
        )
        self.last_dest_label.pack(fill="x", padx=16, pady=(0, 8))

        counts = ctk.CTkFrame(self.status_card, fg_color="transparent")
        counts.pack(fill="x", padx=16, pady=(0, 14))
        self.session_count_label = ctk.CTkLabel(
            counts, text="Session: 0", font=FONT_MONO_SM, text_color=APP_ACCENT,
        )
        self.session_count_label.pack(side="left", padx=(0, 16))
        self.today_count_label = ctk.CTkLabel(
            counts, text="Today: 0", font=FONT_MONO_SM, text_color=APP_TEXT_MUTED,
        )
        self.today_count_label.pack(side="left")

        hdr = ctk.CTkFrame(right, fg_color="transparent")
        hdr.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 6))
        ctk.CTkLabel(hdr, text="Activity log", font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")

        self.watch_path_label = ctk.CTkLabel(
            right, text="", font=FONT_MONO_SM, text_color=APP_TEXT_MUTED, anchor="w",
        )
        self.watch_path_label.grid(row=2, column=0, padx=14, pady=(0, 8), sticky="ew")

        self.log_box = ctk.CTkTextbox(
            right, font=FONT_MONO_SM, fg_color=INPUT_BG, text_color=APP_TEXT_MUTED, wrap="word",
        )
        self.log_box.grid(row=3, column=0, padx=14, pady=(0, 14), sticky="nsew")
        self.log_box.insert("1.0", "Start the watcher to begin monitoring.\n")
        self.log_box.configure(state="disabled")

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, padx=CONTENT_MARGIN, pady=(12, CONTENT_MARGIN))
        self.processed_label = ctk.CTkLabel(footer, text="Files processed this session: 0", text_color=APP_TEXT_MUTED)
        self.processed_label.pack(side="left", padx=(0, 20))
        SecondaryButton(footer, text="Save settings", command=self.save_settings_only, width=120).pack(side="left", padx=4)
        SecondaryButton(footer, text="Create library folders", command=self.create_library, width=160).pack(
            side="left", padx=4,
        )
        self.watch_btn = PrimaryButton(
            footer, text="Start Watcher", width=160, command=self.toggle_watcher,
        )
        self.watch_btn.configure(fg_color=APP_SUCCESS, hover_color=APP_SUCCESS_HOVER)
        self.watch_btn.pack(side="left", padx=(12, 0))

    def _path_row(self, parent, label, variable, browse_cmd, entry_only=False):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=4)
        ctk.CTkLabel(row, text=label, width=100, anchor="w").pack(side="left")
        ctk.CTkEntry(row, textvariable=variable).pack(side="left", fill="x", expand=True, padx=(0, 8))
        if browse_cmd:
            ctk.CTkButton(row, text="Browse", width=80, command=browse_cmd).pack(side="right")

    def _option_row(self, parent, label, variable, values):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=4)
        ctk.CTkLabel(row, text=label, width=100, anchor="w").pack(side="left")
        StyledOptionMenu(row, variable=variable, values=values, width=280).pack(side="left", fill="x", expand=True)

    def _update_poll_label(self, *_):
        self.poll_label.configure(text=f"{self.poll_var.get():.0f}s")

    def browse_library(self):
        path = filedialog.askdirectory()
        if path:
            self.library_root.set(path)

    def _gather_settings(self) -> WatcherSettings:
        existing = load_settings()
        return WatcherSettings(
            library_root=self.library_root.get().strip(),
            inbox_relative=self.inbox_rel.get().strip() or "01_Inbox",
            action=self.action_var.get(),
            poll_seconds=float(self.poll_var.get()),
            layout=self.layout_var.get(),
            date_source=self.date_var.get(),
            scope=self.scope_var.get(),
            name_mode=self.name_var.get(),
            start_on_launch=self.start_on_launch_var.get(),
            run_at_login=self.run_at_login_var.get(),
            minimize_to_tray=self.minimize_tray_var.get(),
            recursive=existing.recursive,
        )

    def rebind_shortcuts(self):
        self.bind_inbox_keys()

    def bind_inbox_keys(self):
        self.unbind_inbox_keys()
        root = self.winfo_toplevel()
        sm = self._shortcut_manager
        if sm:
            bindings = {
                "inbox_toggle": (lambda e: self.toggle_watcher(), "<Control-w>"),
                "inbox_help": (lambda e: self._show_inbox_shortcuts(), "<question>"),
            }
            for action, (handler, default) in bindings.items():
                sm.bind(root, action, default, handler)
            return
        keys = {
            "<Control-w>": lambda e: self.toggle_watcher(),
            "<Control-W>": lambda e: self.toggle_watcher(),
            "<question>": lambda e: self._show_inbox_shortcuts(),
        }
        for seq, handler in keys.items():
            root.bind(seq, handler, add="+")
            self._inbox_key_bindings.append((root, seq, handler))

    def unbind_inbox_keys(self):
        root = self.winfo_toplevel()
        sm = self._shortcut_manager
        if sm:
            sm.unbind_actions(root, ["inbox_toggle", "inbox_help"])
        for root, seq, handler in getattr(self, "_inbox_key_bindings", []):
            try:
                root.unbind(seq, handler)
            except Exception:
                pass
        self._inbox_key_bindings = []

    def _show_inbox_shortcuts(self):
        app = self.app
        if app:
            app._show_shortcuts_help(INBOX_SHORTCUTS, "Inbox Watcher shortcuts")

    def save_settings_only(self):
        settings = self._gather_settings()
        save_settings(settings)
        self.watcher.update_settings(settings)
        ok, msg = set_windows_autostart(settings.run_at_login)
        if not ok:
            messagebox.showwarning("Auto-start", msg)
        self.append_log("Settings saved.")
        self.refresh_status()

    def create_library(self):
        root = self.library_root.get().strip()
        if not root:
            messagebox.showerror("Error", "Enter a library root path first.")
            return
        os.makedirs(root, exist_ok=True)
        OrganizerEngine.ensure_media_library_tree(root)
        os.makedirs(inbox_path(self._gather_settings()), exist_ok=True)
        messagebox.showinfo("Media Library", f"Created folder tree under:\n{root}")

    def toggle_watcher(self):
        if self.watcher.running:
            self.watcher.stop()
            self.refresh_status()
            self.app.status.safe_end_job("Inbox watcher stopped", clear_after_ms=4000)
            return
        settings = self._gather_settings()
        if not settings.library_root:
            messagebox.showerror("Error", "Set a media library root path.")
            return
        save_settings(settings)
        set_windows_autostart(settings.run_at_login)
        ok, msg = self.watcher.start(settings)
        if not ok:
            messagebox.showerror("Watcher", msg)
        else:
            self.app.status.set_job_status(f"Watching {inbox_path(settings)}")
        self.refresh_status()

    def append_log(self, msg: str):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def on_file_processed(self, filepath: str, dest: str):
        """UI update when watcher routes a file."""
        name = os.path.basename(filepath)
        dest_short = truncate_middle(dest, 64)
        self.last_file_label.configure(text=f"Last file: {name}")
        self.last_dest_label.configure(text=f"Routed to: {dest_short}")
        self.refresh_status()
        self.pulse_status_card()

    def pulse_status_card(self):
        if self._pulse_job:
            self.after_cancel(self._pulse_job)
        self._pulse_step = 0
        self._pulse_colors = [INPUT_BG, SIDEBAR_TILE_ACTIVE, BTN_ACTIVE, SIDEBAR_TILE_ACTIVE, INPUT_BG]
        self._pulse_borders = [BORDER, ACCENT, WARNING, ACCENT, BORDER]
        self._run_pulse_step()

    def _run_pulse_step(self):
        step = self._pulse_step
        if step >= len(self._pulse_colors):
            self._pulse_job = None
            return
        self.status_card.configure(
            fg_color=self._pulse_colors[step],
            border_color=self._pulse_borders[step],
        )
        self._pulse_step += 1
        self._pulse_job = self.after(100, self._run_pulse_step)

    def refresh_status(self):
        settings = load_settings()
        watch = inbox_path(settings)
        self.watch_path_label.configure(text=f"Inbox folder: {watch}")
        self.processed_label.configure(text=f"Files processed this session: {self.watcher.files_processed}")
        self.session_count_label.configure(text=f"Session: {self.watcher.files_processed}")
        self.today_count_label.configure(text=f"Today: {self.watcher.files_processed_today}")
        if self.watcher.last_processed_file:
            self.last_file_label.configure(text=f"Last file: {self.watcher.last_processed_file}")
        if self.watcher.last_processed_dest:
            self.last_dest_label.configure(
                text=f"Routed to: {truncate_middle(self.watcher.last_processed_dest, 64)}"
            )
        if self.watcher.running:
            self.status_badge.configure(text="● RUNNING", text_color=SUCCESS)
            self.watch_btn.configure(
                text="Stop Watcher", fg_color=APP_DANGER, hover_color=APP_DANGER_HOVER,
                text_color=TEXT_PRIMARY,
            )
        else:
            self.status_badge.configure(text="● STOPPED", text_color=ERROR)
            self.watch_btn.configure(
                text="Start Watcher", fg_color=APP_SUCCESS, hover_color=APP_SUCCESS_HOVER,
                text_color=TEXT_PRIMARY,
            )

