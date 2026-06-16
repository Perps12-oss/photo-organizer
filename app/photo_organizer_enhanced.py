"""Photo Organizer application shell."""
import customtkinter as ctk
import logging
import os
import time
from tkinter import messagebox

from inbox_watcher import InboxWatcher, TrayController, load_settings
from operation_journal import OperationJournal
from media_gallery import MediaGalleryView, SidecarMappingDialog
from settings_view import SettingsView
from app_settings import load_app_settings, save_app_settings
from idle_scan import IdleDuplicateScanner, resolve_scan_folder, is_system_idle
from keyboard_bindings import shortcuts_reference_text
from core.event_bus import EventBus
from core.shortcut_manager import ShortcutManager
from services.file_operation_service import FileOperationService
from services.metadata_provider import MetadataProvider
from i18n import set_locale, t
from theme import (
    init_fonts, SIDEBAR_WIDTH, CURRENT_PRESET_ID, WINDOW_BG,
    WINDOW_DEFAULT, WINDOW_MIN_H, WINDOW_MIN_W,
)
from theme_manager import GradientBackground, apply_from_settings, apply_preset_tokens, refresh_shell
from ui_components import (
    AppStatusController,
    ModernSidebar,
    StatusBar,
    ToastManager,
    animate_view_enter,
)
from views.home_view import HomeView
from views.duplicate_view import DuplicateView
from views.sort_view import SortView
from views.inbox_view import InboxWatcherView

class PhotoOrganizerApp(ctk.CTk):
    def __init__(self, start_minimized=False, auto_watch=False):
        super().__init__()

        self.title(t("app.title"))
        self.geometry(WINDOW_DEFAULT)
        self.minsize(WINDOW_MIN_W, WINDOW_MIN_H)
        init_fonts(self)
        apply_from_settings()
        self.configure(fg_color=WINDOW_BG)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._bg_layer = GradientBackground(self, preset_id=CURRENT_PRESET_ID)
        self._bg_layer.grid(row=0, column=0, sticky="nsew")
        self._bg_layer.grid_columnconfigure(1, weight=1)
        self._bg_layer.grid_rowconfigure(0, weight=1)
        self._bg_layer.grid_rowconfigure(1, weight=0)
        self._start_minimized = start_minimized
        self._auto_watch = auto_watch
        self._tray_hidden = False

        self.event_bus = EventBus()
        self.shortcut_manager = ShortcutManager()
        self.toast = ToastManager(self)
        self.op_journal = OperationJournal.load()
        self.file_ops = FileOperationService(self.op_journal)
        self.metadata_provider = MetadataProvider()

        settings = load_app_settings()
        set_locale(settings.locale)

        self.watcher = InboxWatcher(on_log=self._on_watcher_log, on_processed=self._on_watcher_processed)
        self.tray = TrayController(
            on_show=self._show_from_tray,
            on_toggle_watch=self._tray_toggle_watch,
            on_quit=self._quit_app,
            is_watching=lambda: self.watcher.running,
            get_stats=lambda: (self.watcher.files_processed, self.watcher.files_processed_today),
        )
        if self.tray.available():
            self.tray.start()

        # Grid layout: sidebar | main ; status bar spans both columns
        # Sidebar Navigation
        nav_specs = [
            ("home", t("nav.home"), self.show_home_frame),
            ("duplicates", t("nav.duplicates"), self.show_duplicate_frame),
            ("gallery", t("nav.gallery"), self.show_gallery_frame),
            ("organizer", t("nav.organizer"), self.show_sort_frame),
            ("inbox", t("nav.inbox"), self.show_inbox_frame),
            ("settings", t("nav.settings"), self.show_settings_frame),
        ]
        self.sidebar_frame = ModernSidebar(self._bg_layer, nav_specs, SIDEBAR_WIDTH)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self._nav_buttons = self.sidebar_frame.nav_buttons
        self._global_key_bindings: list[tuple] = []
        self._wire_event_bus()

        # Main Area Frames
        self.main_frame = ctk.CTkFrame(self._bg_layer, corner_radius=0, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew")
        self.main_frame.grid_rowconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)

        self.status_bar = StatusBar(self._bg_layer)
        self.status_bar.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.status = AppStatusController(self, self.status_bar, self.sidebar_frame)

        self.home_frame = None
        self.duplicate_frame = None
        self.gallery_frame = None
        self.sort_frame = None
        self.inbox_frame = None
        self.settings_frame = None
        self._active_view = None

        self.idle_dup_scanner = IdleDuplicateScanner(
            self,
            should_scan=self._should_idle_duplicate_scan,
            start_scan=self._start_idle_duplicate_scan,
            is_scan_running=self._is_duplicate_scan_running,
            get_cooldown_remaining=self._idle_scan_cooldown_remaining,
        )
        self._sync_idle_duplicate_scanner()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._bind_global_keys()
        self.show_home_frame()
        self.after(0, self._bg_layer._on_configure)

        if self._auto_watch or load_settings().start_on_launch:
            self.after(800, self._auto_start_watcher)
        if self._start_minimized:
            self.after(200, self._hide_to_tray)

    def _on_watcher_log(self, msg: str):
        self.status.safe_status(msg, clear_after_ms=4000)
        if self.inbox_frame:
            self.after(0, self.inbox_frame.append_log, msg)

    def _on_watcher_processed(self, filepath: str, dest: str):
        if self.inbox_frame:
            self.after(0, self.inbox_frame.on_file_processed, filepath, dest)
        name = os.path.basename(filepath)
        self.status.safe_job_status(f"Routed: {name}")
        self.after(2500, lambda: self.status.end_job(f"Watching inbox — {self.watcher.files_processed_today} today"))

    def _show_from_tray(self):
        self.deiconify()
        self.lift()
        self._tray_hidden = False

    def _hide_to_tray(self):
        if self.tray.available() and load_settings().minimize_to_tray:
            self.withdraw()
            self._tray_hidden = True
            self.tray.notify("Photo Organizer", "Running in the system tray.")
        else:
            self.iconify()

    def _tray_toggle_watch(self):
        if self.watcher.running:
            self.watcher.stop()
        else:
            settings = load_settings()
            self.watcher.start(settings)
        if self.inbox_frame:
            self.after(0, self.inbox_frame.refresh_status)

    def _quit_app(self):
        if self.watcher.running:
            self.watcher.stop()
        self.tray.stop()
        self.destroy()

    def _on_close(self):
        settings = load_settings()
        if self.watcher.running and settings.minimize_to_tray and self.tray.available():
            self._hide_to_tray()
            return
        self._quit_app()

    def _auto_start_watcher(self):
        settings = load_settings()
        if settings.library_root.strip():
            ok, msg = self.watcher.start(settings)
            if self.inbox_frame:
                self.inbox_frame.refresh_status()
            if ok:
                self.tray.notify("Inbox Watcher", "Auto-started.")

    def _highlight_nav(self, active_key):
        self.sidebar_frame.highlight(active_key)

    def set_sidebar_scanning(self, scanning: bool, message: str = "Ready"):
        self.sidebar_frame.set_footer_status(message, scanning=scanning)
        self.status_bar.set_scanning(scanning)
        self.status.set_scanning(scanning)
        if scanning:
            self.status_bar.set_center(message)
        else:
            self.status_bar.set_center("")

    def set_status(self, message: str, **kwargs):
        self.status.set_status(message, **kwargs)

    def safe_status(self, message: str, **kwargs):
        self.status.safe_status(message, **kwargs)

    def set_navigation_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        for nav in self._nav_buttons.values():
            nav.configure_state(state)

    def change_appearance_mode_event(self, new_appearance_mode: str):
        ctk.set_appearance_mode(new_appearance_mode)
        refresh_shell(self)
        settings = load_app_settings()
        settings.appearance_mode = new_appearance_mode
        save_app_settings(settings)

    def change_theme_preset_event(self, preset_id: str, custom_accent: str = ""):
        settings = load_app_settings()
        accent = custom_accent if custom_accent else settings.custom_accent
        apply_preset_tokens(preset_id, accent)
        refresh_shell(self)
        settings.theme_preset = preset_id
        if custom_accent:
            settings.custom_accent = custom_accent
        save_app_settings(settings)

    def _wire_event_bus(self):
        self.event_bus.subscribe("toast", lambda message, **_: self.toast.show(message))
        self.event_bus.subscribe("status", lambda message, **kw: self.status.set_status(message, **kw))
        self.event_bus.subscribe("nav.duplicates", lambda **_: self.show_duplicate_frame())

    def _unbind_global_keys(self):
        pass

    def _bind_global_keys(self):
        root = self
        sm = self.shortcut_manager
        global_actions = [
            "nav_home", "nav_duplicates", "nav_gallery", "nav_organizer", "nav_inbox",
            "nav_settings", "shortcuts_help", "undo", "redo",
        ]
        sm.unbind_actions(root, global_actions)
        actions = {
            "nav_home": (lambda e: self.show_home_frame(), "<Control-Key-1>"),
            "nav_duplicates": (lambda e: self.show_duplicate_frame(), "<Control-Key-2>"),
            "nav_gallery": (lambda e: self.show_gallery_frame(), "<Control-Key-3>"),
            "nav_organizer": (lambda e: self.show_sort_frame(), "<Control-Key-4>"),
            "nav_inbox": (lambda e: self.show_inbox_frame(), "<Control-Key-5>"),
            "nav_settings": (lambda e: self.show_settings_frame(), "<Control-comma>"),
            "shortcuts_help": (
                lambda e: self._show_shortcuts_help(shortcuts_reference_text(), "Keyboard shortcuts"),
                "<F1>",
            ),
            "undo": (lambda e: self._undo_last_operation(), "<Control-z>"),
            "redo": (lambda e: self._redo_last_operation(), "<Control-y>"),
        }
        for action, (handler, default) in actions.items():
            sm.bind(root, action, default, handler)

    def _show_shortcuts_help(self, text: str, title: str = "Keyboard shortcuts"):
        messagebox.showinfo(title, text)

    def _undo_last_operation(self):
        ok, msg = self.op_journal.undo_last()
        if ok:
            self.toast.show(msg)
            self.status.safe_end_job(f"Undone: {msg}", clear_after_ms=4000)
        else:
            self.toast.show(msg)

    def _redo_last_operation(self):
        ok, msg = self.op_journal.redo_last()
        if ok:
            self.toast.show(msg)
            self.status.safe_end_job(f"Redone: {msg}", clear_after_ms=4000)
        else:
            self.toast.show(msg)

    def _sync_gallery_settings(self):
        settings = load_app_settings()
        set_locale(settings.locale)
        if self.gallery_frame:
            self.gallery_frame.apply_app_settings()
        self.shortcut_manager.rebind_all()
        if self.duplicate_frame and hasattr(self.duplicate_frame, "rebind_shortcuts"):
            self.duplicate_frame.rebind_shortcuts()
        if self.sort_frame and hasattr(self.sort_frame, "rebind_shortcuts"):
            self.sort_frame.rebind_shortcuts()
        if self.inbox_frame and hasattr(self.inbox_frame, "rebind_shortcuts"):
            self.inbox_frame.rebind_shortcuts()
        if self.gallery_frame and hasattr(self.gallery_frame, "rebind_shortcuts"):
            self.gallery_frame.rebind_shortcuts()

    def _sync_idle_duplicate_scanner(self):
        enabled = load_app_settings().idle_duplicate_scan_enabled
        self.idle_dup_scanner.set_enabled(enabled)

    def _should_idle_duplicate_scan(self) -> bool:
        settings = load_app_settings()
        if not settings.idle_duplicate_scan_enabled:
            return False
        folder = resolve_scan_folder(settings.idle_duplicate_scan_folder)
        if not folder or not os.path.isdir(folder):
            return False
        return is_system_idle(
            settings.idle_duplicate_scan_idle_minutes,
            self._tray_hidden,
            only_when_locked=settings.idle_duplicate_scan_only_when_locked,
            skip_on_battery=settings.idle_duplicate_scan_skip_on_battery,
            max_cpu_percent=settings.idle_duplicate_scan_cpu_limit,
        )

    def _idle_scan_cooldown_remaining(self) -> float:
        settings = load_app_settings()
        elapsed = time.time() - settings.last_idle_duplicate_scan_at
        need = settings.idle_duplicate_scan_cooldown_hours * 3600
        return max(0.0, need - elapsed)

    def _is_duplicate_scan_running(self) -> bool:
        return bool(self.duplicate_frame and self.duplicate_frame.is_scan_running())

    def _start_idle_duplicate_scan(self):
        settings = load_app_settings()
        folder = resolve_scan_folder(settings.idle_duplicate_scan_folder)
        if not folder or not os.path.isdir(folder):
            return
        if not self.duplicate_frame:
            self.duplicate_frame = DuplicateView(
                self.main_frame, app=self, file_ops=self.file_ops, shortcut_manager=self.shortcut_manager,
            )
        self.duplicate_frame.folder_path.set(folder)
        settings.last_idle_duplicate_scan_at = time.time()
        save_app_settings(settings)
        self.duplicate_frame.start_scan_thread(
            max_age_days=settings.idle_duplicate_scan_days,
            silent=True,
            on_complete=self._on_idle_duplicate_scan_done,
        )
        self.safe_status(
            f"Background duplicate scan started (last {settings.idle_duplicate_scan_days} days)…",
            clear_after_ms=5000,
        )

    def _on_idle_duplicate_scan_done(self, dup_count: int, total_count: int, skipped_count: int):
        days = load_app_settings().idle_duplicate_scan_days
        if dup_count > 0:
            msg = f"Found {dup_count} duplicate group(s) in the last {days} days ({total_count:,} files checked)"
            self.toast.show_action(msg, "Review", self.show_duplicate_frame, duration_ms=8000)
            self.event_bus.publish("toast", message=msg)
            self.tray.notify("Photo Organizer — Duplicates", msg)
            self.safe_status(msg, clear_after_ms=8000)
        else:
            note = f"Idle scan complete — no duplicates in the last {days} days"
            self.tray.notify("Photo Organizer", note)
            self.safe_status(note, clear_after_ms=5000)

    def _open_sidecar_mapping_from_settings(self):
        def on_saved():
            if self.settings_frame:
                self.settings_frame.reload()
            if self.gallery_frame:
                self.gallery_frame.apply_app_settings()
        SidecarMappingDialog(self, on_saved=on_saved)

    def hide_all_frames(self):
        if self.duplicate_frame:
            self.duplicate_frame.unbind_review_keys()
        if self.gallery_frame:
            self.gallery_frame.unbind_gallery_keys()
        if self.sort_frame:
            self.sort_frame.unbind_organizer_keys()
        if self.inbox_frame:
            self.inbox_frame.unbind_inbox_keys()
        if self.home_frame:
            self.home_frame.grid_forget()
        if self.duplicate_frame:
            self.duplicate_frame.grid_forget()
        if self.gallery_frame:
            self.gallery_frame.grid_forget()
        if self.sort_frame:
            self.sort_frame.grid_forget()
        if self.inbox_frame:
            self.inbox_frame.grid_forget()
        if self.settings_frame:
            self.settings_frame.grid_forget()

    def show_home_frame(self):
        self.hide_all_frames()
        if not self.home_frame:
            self.home_frame = HomeView(
                self.main_frame,
                on_duplicates=self.show_duplicate_frame,
                on_sort=self.show_sort_frame,
                on_inbox=self.show_inbox_frame,
                on_gallery=self.show_gallery_frame,
                on_settings=self.show_settings_frame,
            )
        self.home_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self._highlight_nav("home")
        self._active_view = "home"
        animate_view_enter(self, self.status_bar)

    def show_duplicate_frame(self):
        self.hide_all_frames()
        if not self.duplicate_frame:
            self.duplicate_frame = DuplicateView(
                self.main_frame, app=self, file_ops=self.file_ops, shortcut_manager=self.shortcut_manager,
            )
        self.duplicate_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.duplicate_frame.bind_review_keys()
        self._highlight_nav("duplicates")
        self._active_view = "duplicates"
        self.set_status("Find Duplicates — select a folder and scan", clear_after_ms=3000)
        animate_view_enter(self, self.status_bar)

    def show_gallery_frame(self, folder: str = ""):
        self.hide_all_frames()
        if not self.gallery_frame:
            library_root = load_settings().library_root
            self.gallery_frame = MediaGalleryView(
                self.main_frame,
                library_root=library_root,
                on_toast=self.toast.show,
                on_status=self.safe_status,
                shortcut_manager=self.shortcut_manager,
                metadata_provider=self.metadata_provider,
            )
        self.gallery_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self.gallery_frame.on_view_shown()
        if folder:
            self.gallery_frame.open_folder(folder)
        self._highlight_nav("gallery")
        self._active_view = "gallery"
        self.set_status("Media Gallery", clear_after_ms=2000)
        animate_view_enter(self, self.status_bar)

    def open_folder_in_gallery(self, folder: str):
        """Switch to Media Gallery and load the given folder."""
        if not folder or not os.path.isdir(folder):
            messagebox.showinfo("Media Gallery", "Folder does not exist or is not set yet.")
            return
        self.show_gallery_frame(folder=folder)

    def show_sort_frame(self):
        self.hide_all_frames()
        if not self.sort_frame:
            self.sort_frame = SortView(
                self.main_frame,
                on_open_gallery=self.open_folder_in_gallery,
                shortcut_manager=self.shortcut_manager,
            )
        self.sort_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self.sort_frame.on_view_shown()
        self.sort_frame.bind_organizer_keys()
        self._highlight_nav("organizer")
        self._active_view = "organizer"
        animate_view_enter(self, self.status_bar)

    def show_settings_frame(self):
        self.hide_all_frames()
        if not self.settings_frame:
            self.settings_frame = SettingsView(
                self.main_frame,
                on_theme_change=self.change_appearance_mode_event,
                on_theme_preset_change=self.change_theme_preset_event,
                on_gallery_settings_saved=self._sync_gallery_settings,
                on_open_sidecar_mapping=self._open_sidecar_mapping_from_settings,
                on_open_inbox=self.show_inbox_frame,
                on_toast=self.toast.show,
                on_idle_scan_saved=self._sync_idle_duplicate_scanner,
                shortcut_manager=self.shortcut_manager,
            )
        else:
            self.settings_frame.reload()
        self.settings_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self._highlight_nav("settings")
        self._active_view = "settings"
        self.set_status("Settings", clear_after_ms=2000)
        animate_view_enter(self, self.status_bar)

    def show_inbox_frame(self):
        self.hide_all_frames()
        if not self.inbox_frame:
            self.inbox_frame = InboxWatcherView(
                self.main_frame, self.watcher, self, shortcut_manager=self.shortcut_manager,
            )
        self.inbox_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self.inbox_frame.refresh_status()
        self.inbox_frame.bind_inbox_keys()
        self._highlight_nav("inbox")
        self._active_view = "inbox"
        animate_view_enter(self, self.status_bar)
        if self.watcher.running:
            self.set_status(
                f"Inbox watcher running — {self.watcher.files_processed_today} file(s) today",
                clear_after_ms=4000,
            )
        else:
            self.set_status("Inbox Watcher — configure paths and start", clear_after_ms=3000)



if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    import argparse

    from config_bootstrap import bootstrap_config, show_ffmpeg_missing_dialog, show_startup_issues_dialog

    parser = argparse.ArgumentParser(description="Photo Organizer")
    parser.add_argument("--minimized", action="store_true", help="Start minimized to system tray")
    parser.add_argument("--auto-watch", action="store_true", dest="auto_watch", help="Start inbox watcher on launch")
    args = parser.parse_args()

    bootstrap_result = bootstrap_config()
    ctk.set_appearance_mode(bootstrap_result.app_settings.appearance_mode)
    ctk.set_default_color_theme("blue")
    apply_preset_tokens(
        bootstrap_result.app_settings.theme_preset,
        bootstrap_result.app_settings.custom_accent,
    )

    app = PhotoOrganizerApp(start_minimized=args.minimized, auto_watch=args.auto_watch)
    app.after(150, lambda: show_startup_issues_dialog(app, bootstrap_result))
    app.after(450, lambda: show_ffmpeg_missing_dialog(app, bootstrap_result.app_settings))
    app.mainloop()
