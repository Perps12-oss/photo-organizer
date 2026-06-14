"""
Shared UI shell components: sidebar nav, status bar, toasts.
"""
from __future__ import annotations

from typing import Callable, Optional

import customtkinter as ctk

from theme import (
    ANIM_FADE_MS,
    ANIM_VIEW_MS,
    APP_ACCENT,
    APP_ACCENT_HOVER,
    APP_BORDER,
    APP_CARD,
    APP_PRIMARY,
    APP_PRIMARY_TEXT,
    APP_SECONDARY,
    APP_SIDEBAR,
    APP_SURFACE,
    APP_TEXT,
    APP_TEXT_MUTED,
    BTN_HOVER,
    BTN_INACTIVE,
    BTN_INACTIVE_HOVER,
    CARD_RADIUS,
    FONT_BODY,
    FONT_HEADING,
    FONT_MONO_SM,
    FONT_SMALL,
    PAD_LG,
    PAD_MD,
    PAD_SM,
    STATUS_IDLE,
    STATUS_INFO,
    STATUS_JOB,
    toast_colors,
)

# Plain-text nav — no emoji (consistent across Windows versions)
NAV_ICONS: dict[str, str] = {}

GLOBAL_SHORTCUTS = (
    "Navigation\n"
    "Ctrl+1   Home\n"
    "Ctrl+2   Find Duplicates\n"
    "Ctrl+3   Media Gallery\n"
    "Ctrl+4   File Organizer\n"
    "Ctrl+5   Inbox Watcher\n"
    "Ctrl+,   Settings\n"
    "Ctrl+Z   Undo last file operation\n"
    "Ctrl+Y   Redo last undone operation\n"
    "F1       Keyboard shortcuts\n"
    "Esc      Home (from most views)"
)

GALLERY_SHORTCUTS = (
    "← / →   Previous / next photo\n"
    "0–5     Set star rating\n"
    "F       Fullscreen lightbox (video: play/pause with Space)\n"
    "Ctrl+S  Save metadata now\n"
    "Ctrl+O  Browse for folder\n"
    "?       Show gallery shortcuts"
)

ORGANIZER_SHORTCUTS = (
    "Ctrl+P        Preview organization\n"
    "Ctrl+Enter    Start organizing\n"
    "?             Show organizer shortcuts"
)

INBOX_SHORTCUTS = (
    "Ctrl+W   Start / stop watcher\n"
    "?        Show inbox shortcuts"
)

DUPLICATE_SHORTCUTS = (
    "↑ / ↓   Previous / next duplicate group\n"
    "← / →   Previous / next image in group\n"
    "Space   Toggle mark for deletion\n"
    "Enter   Smart Best (keep best, mark rest)\n"
    "Delete  Delete marked files\n"
    "?       Show duplicate shortcuts\n"
    "Esc     Return to Home"
)


class EmptyState(ctk.CTkFrame):
    """Centered placeholder with icon, title, subtitle, and optional action."""

    def __init__(
        self,
        parent,
        icon: str = "📂",
        title: str = "Nothing here yet",
        subtitle: str = "",
        action_text: Optional[str] = None,
        action: Optional[Callable[[], None]] = None,
        **kwargs,
    ):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._action_btn: Optional[ctk.CTkButton] = None
        self.icon_label = ctk.CTkLabel(self, text=icon, font=ctk.CTkFont(size=64))
        self.icon_label.pack(pady=(PAD_LG, PAD_SM))
        self.title_label = ctk.CTkLabel(
            self, text=title, font=ctk.CTkFont(size=17, weight="bold"), text_color=APP_TEXT,
        )
        self.title_label.pack(pady=(0, PAD_SM))
        self.subtitle_label = ctk.CTkLabel(
            self, text=subtitle, font=FONT_SMALL, text_color=APP_TEXT_MUTED,
            justify="center", wraplength=420,
        )
        self.subtitle_label.pack(pady=(0, PAD_MD))
        if action_text and action:
            self._action_btn = ctk.CTkButton(
                self, text=action_text, width=160, height=34,
                fg_color=APP_ACCENT, text_color="#0a0a12", hover_color="#00ccaa",
                command=action,
            )
            self._action_btn.pack(pady=(PAD_SM, PAD_LG))

    def set_content(
        self,
        icon: Optional[str] = None,
        title: Optional[str] = None,
        subtitle: Optional[str] = None,
        action_text: Optional[str] = None,
        action: Optional[Callable[[], None]] = None,
    ):
        if icon is not None:
            self.icon_label.configure(text=icon)
        if title is not None:
            self.title_label.configure(text=title)
        if subtitle is not None:
            self.subtitle_label.configure(text=subtitle)
        if action_text and action:
            if self._action_btn is None:
                self._action_btn = ctk.CTkButton(
                    self, text=action_text, width=160, height=34,
                    fg_color=APP_ACCENT, text_color="#0a0a12", hover_color="#00ccaa",
                    command=action,
                )
            else:
                self._action_btn.configure(text=action_text, command=action)
            self._action_btn.pack(pady=(PAD_SM, PAD_LG))
        elif self._action_btn is not None:
            self._action_btn.pack_forget()


class SettingsSection(ctk.CTkFrame):
    """Card section for the Settings page."""

    def __init__(self, parent, title: str, subtitle: str = "", **kwargs):
        super().__init__(
            parent, fg_color=APP_CARD, corner_radius=CARD_RADIUS,
            border_width=1, border_color=APP_BORDER, **kwargs,
        )
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=PAD_LG, pady=(PAD_LG, PAD_SM))
        ctk.CTkLabel(header, text=title, font=FONT_HEADING, anchor="w").pack(anchor="w")
        if subtitle:
            ctk.CTkLabel(
                header, text=subtitle, font=FONT_SMALL, text_color=APP_TEXT_MUTED,
                anchor="w", justify="left", wraplength=700,
            ).pack(anchor="w", pady=(4, 0))
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="x", padx=PAD_LG, pady=(0, PAD_LG))


class SidebarNavButton(ctk.CTkFrame):
    """Sidebar item with left accent strip and icon label."""

    def __init__(self, parent, text: str, nav_key: str, command: Callable[[], None], **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.nav_key = nav_key
        self._command = command

        self.indicator = ctk.CTkFrame(self, width=4, corner_radius=2, fg_color="transparent")
        self.indicator.pack(side="left", fill="y", padx=(0, 4))

        self.button = ctk.CTkButton(
            self,
            text=f"  {text}",
            anchor="w",
            height=40,
            corner_radius=8,
            font=ctk.CTkFont(size=13),
            fg_color="transparent",
            hover_color=BTN_HOVER,
            text_color=APP_TEXT,
            command=command,
        )
        self.button.pack(side="left", fill="x", expand=True)

    def set_active(self, active: bool):
        if active:
            self.indicator.configure(fg_color=APP_ACCENT)
            self.button.configure(
                fg_color=BTN_HOVER,
                hover_color=BTN_HOVER,
                text_color=APP_TEXT,
            )
        else:
            self.indicator.configure(fg_color="transparent")
            self.button.configure(
                fg_color="transparent",
                hover_color=BTN_INACTIVE_HOVER,
                text_color=APP_TEXT,
            )

    def configure_state(self, state: str):
        self.button.configure(state=state)


class StatusBar(ctk.CTkFrame):
    """Global footer status strip."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, height=30, corner_radius=0, fg_color=APP_SIDEBAR, **kwargs)
        self.grid_propagate(False)
        self.label = ctk.CTkLabel(
            self, text="Ready", anchor="w", font=FONT_BODY, text_color=APP_TEXT_MUTED,
        )
        self.label.pack(side="left", padx=12, pady=4)


def animate_view_enter(root: ctk.CTk, status_bar: Optional["StatusBar"] = None):
    """Brief accent flash on the status bar when switching views."""
    if not status_bar:
        return
    original = status_bar.cget("fg_color")
    status_bar.configure(fg_color="#1a3a32")
    root.after(ANIM_VIEW_MS, lambda: status_bar.configure(fg_color=original))


class ToastManager:
    """Single visible toast with a short queue."""

    MAX_QUEUE = 3

    def __init__(self, root: ctk.CTk):
        self.root = root
        self._queue: list[tuple[str, int]] = []
        self._showing = False
        self._window: Optional[ctk.CTkToplevel] = None
        self._label: Optional[ctk.CTkLabel] = None
        self._dismiss_job: Optional[int] = None

    def show(self, message: str, duration_ms: int = 1500):
        if len(self._queue) >= self.MAX_QUEUE:
            self._queue.pop(0)
        self._queue.append((message, duration_ms, None, None))
        if not self._showing:
            self._show_next()

    def show_action(
        self,
        message: str,
        action_text: str,
        action_callback,
        duration_ms: int = 6000,
    ):
        if len(self._queue) >= self.MAX_QUEUE:
            self._queue.pop(0)
        self._queue.append((message, duration_ms, action_text, action_callback))
        if not self._showing:
            self._show_next()

    def _show_next(self):
        if not self._queue:
            self._showing = False
            self._destroy_window()
            return
        message, duration_ms, action_text, action_callback = self._queue.pop(0)
        self._showing = True
        bg, text, border = toast_colors()

        self._destroy_window()
        self._window = ctk.CTkToplevel(self.root)
        self._window.overrideredirect(True)
        self._window.attributes("-topmost", True)
        try:
            self._window.attributes("-alpha", 0.0)
        except Exception:
            pass
        frame = ctk.CTkFrame(
            self._window, fg_color=bg, corner_radius=8,
            border_width=1, border_color=border,
        )
        frame.pack(padx=2, pady=2)
        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(padx=16, pady=10)
        self._label = ctk.CTkLabel(row, text=message, text_color=text, font=FONT_BODY)
        self._label.pack(side="left", padx=(0, 12))
        if action_text and action_callback:
            ctk.CTkButton(
                row, text=action_text, width=80, height=28,
                fg_color=APP_ACCENT, text_color="#0a0a12", hover_color=APP_ACCENT_HOVER,
                command=lambda: (action_callback(), self._dismiss_current()),
            ).pack(side="left")
        self._position_window()
        self._fade_toast_in(0.0)
        if self._dismiss_job:
            self.root.after_cancel(self._dismiss_job)
        self._dismiss_job = self.root.after(duration_ms, self._dismiss_current)

    def _fade_toast_in(self, alpha: float):
        if not self._window or not self._window.winfo_exists():
            return
        try:
            self._window.attributes("-alpha", min(0.96, alpha))
        except Exception:
            return
        if alpha < 0.96:
            step = 0.96 / max(1, ANIM_FADE_MS // 24)
            self.root.after(24, lambda: self._fade_toast_in(alpha + step))

    def _position_window(self):
        if not self._window or not self._window.winfo_exists():
            return
        self.root.update_idletasks()
        rx = self.root.winfo_rootx()
        ry = self.root.winfo_rooty()
        rw = self.root.winfo_width()
        rh = self.root.winfo_height()
        self._window.update_idletasks()
        tw = max(self._window.winfo_reqwidth(), 120)
        th = self._window.winfo_reqheight()
        x = rx + (rw - tw) // 2
        y = ry + rh - th - 48
        self._window.geometry(f"+{x}+{y}")

    def _dismiss_current(self):
        self._dismiss_job = None
        self._destroy_window()
        self._showing = False
        if self._queue:
            self.root.after(80, self._show_next)

    def _destroy_window(self):
        if self._window and self._window.winfo_exists():
            self._window.destroy()
        self._window = None
        self._label = None

    def refresh_theme(self):
        if self._showing and self._window and self._window.winfo_exists():
            bg, text, border = toast_colors()
            for child in self._window.winfo_children():
                if isinstance(child, ctk.CTkFrame):
                    child.configure(fg_color=bg, border_color=border)
            if self._label:
                self._label.configure(text_color=text)


class AppStatusController:
    """Thread-safe status updates with priority tiers."""

    def __init__(self, root: ctk.CTk, status_bar: StatusBar):
        self.root = root
        self.status_bar = status_bar
        self._priority = STATUS_IDLE
        self._clear_job: Optional[str] = None

    def set_status(
        self,
        message: str,
        priority: int = STATUS_INFO,
        clear_after_ms: Optional[int] = None,
    ):
        if priority < self._priority:
            return
        self._priority = priority
        self.status_bar.label.configure(text=message)
        if self._clear_job:
            self.root.after_cancel(self._clear_job)
            self._clear_job = None
        if clear_after_ms is not None:
            self._clear_job = self.root.after(clear_after_ms, self._reset_idle)

    def safe_status(
        self,
        message: str,
        priority: int = STATUS_INFO,
        clear_after_ms: Optional[int] = None,
    ):
        self.root.after(0, lambda: self.set_status(message, priority, clear_after_ms))

    def set_job_status(self, message: str):
        self.set_status(message, priority=STATUS_JOB)

    def safe_job_status(self, message: str):
        self.safe_status(message, priority=STATUS_JOB)

    def end_job(self, message: str, clear_after_ms: Optional[int] = 5000):
        """Drop job priority so post-scan messages can appear."""
        self._priority = STATUS_IDLE
        self.set_status(message, priority=STATUS_INFO, clear_after_ms=clear_after_ms)

    def safe_end_job(self, message: str, clear_after_ms: Optional[int] = 5000):
        self.root.after(0, lambda: self.end_job(message, clear_after_ms))

    def _reset_idle(self):
        self._priority = STATUS_IDLE
        self.status_bar.label.configure(text="Ready")
        self._clear_job = None


class VirtualGroupList(ctk.CTkFrame):
    """Canvas-virtualized duplicate group list for large scan results."""

    ROW_HEIGHT = 52

    def __init__(
        self,
        parent,
        on_select: Optional[Callable[[int], None]] = None,
        **kwargs,
    ):
        super().__init__(parent, fg_color=APP_SURFACE, corner_radius=CARD_RADIUS, **kwargs)
        self._on_select = on_select
        self._groups: list[tuple[str, list[str], str, float]] = []
        self._selected = -1
        self._row_widgets: list[ctk.CTkButton] = []
        self._visible_count = 0
        self._rebuilding = False
        self._scroll_guard = False
        self._last_render_first = -1

        import tkinter as tk
        self._canvas = tk.Canvas(self, bg=APP_SURFACE, highlightthickness=0, bd=0)
        self._canvas.pack(fill="both", expand=True, padx=4, pady=4)
        self._scrollbar = ctk.CTkScrollbar(self, command=self._canvas.yview)
        self._scrollbar.pack(side="right", fill="y")
        self._canvas.configure(yscrollcommand=self._on_yscroll)

        self._inner = ctk.CTkFrame(self._canvas, fg_color="transparent")
        self._canvas_window = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._inner.bind("<Configure>", self._on_inner_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        self.bind("<Enter>", lambda _e: self._bind_mousewheel(True))
        self.bind("<Leave>", lambda _e: self._bind_mousewheel(False))

    def _bind_mousewheel(self, active: bool):
        if active:
            self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        else:
            try:
                self._canvas.unbind_all("<MouseWheel>")
            except Exception:
                pass

    def _on_mousewheel(self, event):
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self._rebuild_visible_rows()

    def _visible_first_index(self) -> int:
        if not self._groups:
            return 0
        try:
            top_frac = self._canvas.yview()[0]
            return int(top_frac * len(self._groups))
        except Exception:
            return 0

    def _on_yscroll(self, first, last):
        self._scrollbar.set(first, last)
        if self._scroll_guard or self._rebuilding or not self._groups:
            return
        first_idx = self._visible_first_index()
        if first_idx == self._last_render_first:
            return
        self._last_render_first = first_idx
        self._rebuild_visible_rows()

    def _update_scrollregion(self):
        self._scroll_guard = True
        try:
            self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        finally:
            self._scroll_guard = False

    def _on_inner_configure(self, _event=None):
        if self._rebuilding:
            return
        self._update_scrollregion()

    def _on_canvas_configure(self, event):
        self._canvas.itemconfig(self._canvas_window, width=event.width)
        if not self._rebuilding:
            self._rebuild_visible_rows()

    def set_groups(
        self,
        groups: list[tuple[str, list[str]]],
        scores: dict[str, float],
        kind_fn: Callable[[str], str],
    ):
        self._groups = []
        for h, paths in groups:
            avg = sum(scores.get(p, 0) for p in paths) / max(len(paths), 1)
            self._groups.append((h, paths, kind_fn(h), avg))
        self._selected = -1
        self._last_render_first = -1
        self._rebuild_visible_rows()

    def _rebuild_visible_rows(self):
        if self._rebuilding:
            return
        self._rebuilding = True
        try:
            self._rebuild_visible_rows_impl()
        finally:
            self._rebuilding = False

    def _rebuild_visible_rows_impl(self):
        for w in self._row_widgets:
            w.destroy()
        self._row_widgets.clear()
        for w in self._inner.winfo_children():
            w.destroy()

        if not self._groups:
            ctk.CTkLabel(
                self._inner, text="No duplicate groups match filters.",
                text_color=APP_TEXT_MUTED, font=FONT_SMALL,
            ).pack(pady=24, padx=12)
            self._update_scrollregion()
            self._last_render_first = -1
            return

        canvas_h = max(self._canvas.winfo_height(), 200)
        self._visible_count = min(len(self._groups), max(8, canvas_h // self.ROW_HEIGHT + 2))

        first = 0
        try:
            top_frac = self._canvas.yview()[0]
            first = int(top_frac * len(self._groups))
        except Exception:
            first = 0
        first = max(0, min(first, max(0, len(self._groups) - self._visible_count)))
        self._last_render_first = first
        end = min(len(self._groups), first + self._visible_count + 4)

        for i in range(first, end):
            h, paths, kind, avg = self._groups[i]
            fg = APP_SECONDARY if i == self._selected else "transparent"
            btn = ctk.CTkButton(
                self._inner,
                text=f"Group {i + 1} ({kind}) — {len(paths)} files · score {avg:.0f}",
                anchor="w",
                height=self.ROW_HEIGHT - 6,
                fg_color=fg,
                hover_color=BTN_HOVER,
                command=lambda idx=i: self._select(idx),
            )
            btn.pack(fill="x", pady=2, padx=4)
            self._row_widgets.append(btn)

        total_h = len(self._groups) * self.ROW_HEIGHT
        spacer = ctk.CTkFrame(self._inner, fg_color="transparent", height=max(0, total_h - (end - first) * self.ROW_HEIGHT))
        if total_h > (end - first) * self.ROW_HEIGHT:
            spacer.pack(fill="x")
        self._update_scrollregion()

    def _select(self, index: int):
        self._selected = index
        self._rebuild_visible_rows()
        if self._on_select:
            self._on_select(index)

    def select_index(self, index: int, fire: bool = True):
        if 0 <= index < len(self._groups):
            self._selected = index
            self._rebuild_visible_rows()
            if fire and self._on_select:
                self._on_select(index)

    def get_group_at(self, index: int) -> Optional[tuple[str, list[str]]]:
        if 0 <= index < len(self._groups):
            h, paths, _, _ = self._groups[index]
            return h, paths
        return None

    def selected_index(self) -> int:
        return self._selected

    def count(self) -> int:
        return len(self._groups)


__all__ = [
    "AppStatusController",
    "DUPLICATE_SHORTCUTS",
    "EmptyState",
    "GALLERY_SHORTCUTS",
    "GLOBAL_SHORTCUTS",
    "INBOX_SHORTCUTS",
    "NAV_ICONS",
    "ORGANIZER_SHORTCUTS",
    "SidebarNavButton",
    "StatusBar",
    "ToastManager",
    "VirtualGroupList",
    "animate_view_enter",
]
