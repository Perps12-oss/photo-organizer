"""Design System V1 — reusable UI primitives."""
from __future__ import annotations

import time
import tkinter as tk
from typing import Callable, Optional

import customtkinter as ctk

from assets import load_icon
from theme import (
    ACCENT,
    ACCENT_HOVER,
    APP_BTN_GHOST,
    APP_PRIMARY_TEXT,
    BODY_FONT,
    BORDER,
    BTN_RADIUS,
    CAPTION_FONT,
    CARD_PADDING,
    CARD_RADIUS,
    CARD_SHADOW,
    CONTROL_GAP,
    CONTENT_MARGIN,
    ERROR,
    INPUT_BG,
    INPUT_RADIUS,
    SECTION_FONT,
    SECTION_GAP,
    SUCCESS,
    SURFACE_BG,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TITLE_FONT,
)

NAV_ICON_MAP = {
    "home": "home",
    "duplicates": "search",
    "gallery": "image",
    "organizer": "folder",
    "inbox": "inbox",
    "settings": "settings",
}


class ElevatedCard(ctk.CTkFrame):
    """Fake shadow + bordered surface card."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.shadow = ctk.CTkFrame(self, fg_color=CARD_SHADOW, corner_radius=CARD_RADIUS)
        self.shadow.pack(fill="both", expand=True, padx=0, pady=(2, 0))
        self.card = ctk.CTkFrame(
            self.shadow,
            fg_color=SURFACE_BG,
            corner_radius=CARD_RADIUS,
            border_width=1,
            border_color=BORDER,
        )
        self.card.pack(fill="both", expand=True, padx=0, pady=(0, 2))
        self.body = ctk.CTkFrame(self.card, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=CARD_PADDING, pady=CARD_PADDING)


class PageHeader(ctk.CTkFrame):
    def __init__(self, parent, title: str, subtitle: str = "", **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        ctk.CTkLabel(self, text=title, font=TITLE_FONT, text_color=TEXT_PRIMARY, anchor="w").pack(
            anchor="w"
        )
        if subtitle:
            ctk.CTkLabel(
                self, text=subtitle, font=BODY_FONT, text_color=TEXT_SECONDARY, anchor="w",
            ).pack(anchor="w", pady=(4, 0))


class ViewPage(ctk.CTkFrame):
    """Standard page wrapper with header row and expanding body."""

    def __init__(self, parent, title: str = "", subtitle: str = "", **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        pad = CONTENT_MARGIN
        if title:
            self.header = PageHeader(self, title, subtitle)
            self.header.grid(row=0, column=0, sticky="ew", padx=pad, pady=(pad, SECTION_GAP))
        else:
            self.header = None
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=1, column=0, sticky="nsew", padx=pad, pady=(0, pad))


class PrimaryButton(ctk.CTkButton):
    def __init__(self, parent, text: str = "", command=None, icon: Optional[str] = None, **kwargs):
        img = load_icon(icon, 20, APP_PRIMARY_TEXT) if icon else None
        super().__init__(
            parent,
            text=text,
            command=command,
            height=kwargs.pop("height", 46),
            corner_radius=BTN_RADIUS,
            font=SECTION_FONT,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color=APP_PRIMARY_TEXT,
            image=img,
            compound="left" if img else "center",
            **kwargs,
        )


class SecondaryButton(ctk.CTkButton):
    def __init__(self, parent, text: str = "", command=None, **kwargs):
        super().__init__(
            parent,
            text=text,
            command=command,
            height=kwargs.pop("height", 40),
            corner_radius=BTN_RADIUS,
            font=BODY_FONT,
            fg_color=APP_BTN_GHOST,
            hover_color=INPUT_BG,
            border_width=1,
            border_color=BORDER,
            text_color=TEXT_PRIMARY,
            **kwargs,
        )


class GhostButton(ctk.CTkButton):
    def __init__(self, parent, text: str = "", command=None, **kwargs):
        super().__init__(
            parent,
            text=text,
            command=command,
            height=kwargs.pop("height", 32),
            corner_radius=8,
            font=CAPTION_FONT,
            fg_color=APP_BTN_GHOST,
            hover_color=INPUT_BG,
            text_color=TEXT_SECONDARY,
            **kwargs,
        )


class LabeledEntry(ctk.CTkEntry):
    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            height=kwargs.pop("height", 42),
            corner_radius=INPUT_RADIUS,
            border_width=1,
            fg_color=INPUT_BG,
            border_color=BORDER,
            text_color=TEXT_PRIMARY,
            font=BODY_FONT,
            **kwargs,
        )


class StyledOptionMenu(ctk.CTkOptionMenu):
    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            height=kwargs.pop("height", 40),
            corner_radius=INPUT_RADIUS,
            fg_color=INPUT_BG,
            button_color=SURFACE_BG,
            button_hover_color="#30384a",
            dropdown_fg_color=SURFACE_BG,
            dropdown_hover_color="#30384a",
            dropdown_text_color=TEXT_PRIMARY,
            text_color=TEXT_PRIMARY,
            font=BODY_FONT,
            **kwargs,
        )


class StyledCheckBox(ctk.CTkCheckBox):
    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            checkbox_width=22,
            checkbox_height=22,
            corner_radius=6,
            border_width=1,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            border_color=BORDER,
            text_color=TEXT_PRIMARY,
            font=BODY_FONT,
            **kwargs,
        )


class SectionLabel(ctk.CTkLabel):
    def __init__(self, parent, text: str, number: Optional[int] = None, **kwargs):
        label = f"{number}. {text}" if number is not None else text
        super().__init__(
            parent, text=label, font=SECTION_FONT, text_color=TEXT_PRIMARY, anchor="w", **kwargs,
        )


class ModernSlider(ctk.CTkFrame):
    """Canvas-drawn slider with accent track and glow thumb."""

    TRACK_H = 3
    THUMB_R = 8
    GLOW_R = 10

    def __init__(
        self,
        parent,
        from_: float = 0,
        to: float = 100,
        number_of_steps: Optional[int] = None,
        variable: Optional[tk.Variable] = None,
        command: Optional[Callable] = None,
        width: int = 200,
        **kwargs,
    ):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.from_ = from_
        self.to = to
        self.number_of_steps = number_of_steps
        self.variable = variable
        self.command = command
        self._dragging = False
        self._value = float(variable.get()) if variable else from_

        self.canvas = tk.Canvas(
            self, width=width, height=28, bg=SURFACE_BG, highlightthickness=0, bd=0,
        )
        self.canvas.pack(fill="x", expand=True)
        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        if variable:
            variable.trace_add("write", self._on_var_change)

    def _on_var_change(self, *_):
        if self._dragging or not self.variable:
            return
        try:
            self._value = float(self.variable.get())
            self._paint()
        except (tk.TclError, ValueError):
            pass

    def _on_resize(self, _event=None):
        self._paint()

    def _ratio(self) -> float:
        span = self.to - self.from_
        if span <= 0:
            return 0.0
        return max(0.0, min(1.0, (self._value - self.from_) / span))

    def _value_from_x(self, x: float) -> float:
        w = max(self.canvas.winfo_width(), 40)
        pad = self.GLOW_R + 2
        ratio = max(0.0, min(1.0, (x - pad) / max(1, w - 2 * pad)))
        raw = self.from_ + ratio * (self.to - self.from_)
        if self.number_of_steps:
            step = (self.to - self.from_) / self.number_of_steps
            raw = round((raw - self.from_) / step) * step + self.from_
        return max(self.from_, min(self.to, raw))

    def _set_value(self, val: float, notify: bool = True):
        self._value = val
        if self.variable:
            self.variable.set(int(val) if isinstance(self.variable, tk.IntVar) else val)
        self._paint()
        if notify and self.command:
            self.command(val)

    def _on_press(self, event):
        self._dragging = True
        self._set_value(self._value_from_x(event.x))

    def _on_drag(self, event):
        self._set_value(self._value_from_x(event.x))

    def _on_release(self, _event):
        self._dragging = False

    def get(self) -> float:
        return self._value

    def set(self, value: float):
        self._set_value(float(value), notify=False)

    def _paint(self):
        c = self.canvas
        c.delete("all")
        w = max(c.winfo_width(), 40)
        h = 28
        cy = h // 2
        pad = self.GLOW_R + 2
        x0, x1 = pad, w - pad
        ratio = self._ratio()
        mid = x0 + ratio * (x1 - x0)

        c.create_line(x0, cy, x1, cy, fill=BORDER, width=self.TRACK_H, capstyle=tk.ROUND)
        if mid > x0:
            c.create_line(x0, cy, mid, cy, fill=ACCENT, width=self.TRACK_H, capstyle=tk.ROUND)

        gr, gg, gb = _hex_rgb(ACCENT)
        glow = f"#{gr:02x}{gg:02x}{gb:02x}"
        c.create_oval(
            mid - self.GLOW_R, cy - self.GLOW_R, mid + self.GLOW_R, cy + self.GLOW_R,
            fill="", outline=glow, width=1,
        )
        c.create_oval(
            mid - self.THUMB_R, cy - self.THUMB_R, mid + self.THUMB_R, cy + self.THUMB_R,
            fill=TEXT_PRIMARY, outline=ACCENT, width=2,
        )


def _hex_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


class ResultsCard(ElevatedCard):
    """Scan results / empty state with circular success icon."""

    def __init__(self, parent, title: str = "Scan Results", **kwargs):
        super().__init__(parent, **kwargs)
        header = ctk.CTkFrame(self.body, fg_color="transparent")
        header.pack(fill="x", pady=(0, SECTION_GAP))
        icon = load_icon("search", 20, TEXT_SECONDARY)
        if icon:
            ctk.CTkLabel(header, text="", image=icon).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(header, text=title, font=SECTION_FONT, text_color=TEXT_PRIMARY).pack(
            side="left",
        )

        self.center = ctk.CTkFrame(self.body, fg_color="transparent")
        self.center.pack(fill="both", expand=True)
        self.icon_frame = ctk.CTkFrame(self.center, fg_color="transparent", width=72, height=72)
        self.icon_frame.pack(pady=(8, 12))
        self.icon_frame.pack_propagate(False)
        self.status_canvas = tk.Canvas(
            self.icon_frame, width=72, height=72, bg=SURFACE_BG, highlightthickness=0, bd=0,
        )
        self.status_canvas.pack()
        self.title_label = ctk.CTkLabel(
            self.center, text="Ready to scan", font=SECTION_FONT, text_color=TEXT_PRIMARY,
        )
        self.title_label.pack()
        self.subtitle_label = ctk.CTkLabel(
            self.center, text="Select a folder and start a scan.",
            font=BODY_FONT, text_color=TEXT_SECONDARY, wraplength=320, justify="center",
        )
        self.subtitle_label.pack(pady=(6, 12))

        self.stats_frame = ctk.CTkFrame(self.center, fg_color="transparent")
        self.stats_frame.pack(fill="x", pady=(0, 8))

        self.action_btn = SecondaryButton(self.center, text="")
        self.action_frame = ctk.CTkFrame(self.center, fg_color="transparent")
        self.show_idle()

    def _draw_circle_icon(self, color: str, draw_check: bool = False):
        c = self.status_canvas
        c.delete("all")
        cx, cy, r = 36, 36, 32
        c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=color, outline="")
        if draw_check:
            c.create_line(22, 38, 32, 48, 48, 28, fill=TEXT_PRIMARY, width=3, capstyle=tk.ROUND)

    def show_idle(self, subtitle: str = "Select a folder and start a scan."):
        self._draw_circle_icon(INPUT_BG, draw_check=False)
        c = self.status_canvas
        c.create_text(36, 36, text="?", fill=TEXT_SECONDARY, font=("Segoe UI", 20))
        self.title_label.configure(text="Ready to scan")
        self.subtitle_label.configure(text=subtitle)
        self._clear_stats()
        self.action_frame.pack_forget()

    def show_success(
        self,
        title: str,
        subtitle: str,
        stats: Optional[list[tuple[str, str]]] = None,
        action_text: Optional[str] = None,
        action: Optional[Callable] = None,
    ):
        self._draw_circle_icon(SUCCESS, draw_check=True)
        self.title_label.configure(text=title)
        self.subtitle_label.configure(text=subtitle)
        self._set_stats(stats or [])
        if action_text and action:
            self.action_btn.configure(text=action_text, command=action)
            self.action_btn.pack(in_=self.action_frame, fill="x", pady=(8, 0))
            self.action_frame.pack(fill="x", pady=(4, 0))
        else:
            self.action_frame.pack_forget()

    def show_error(self, title: str, subtitle: str):
        self._draw_circle_icon(ERROR, draw_check=False)
        self.title_label.configure(text=title)
        self.subtitle_label.configure(text=subtitle)
        self._clear_stats()
        self.action_frame.pack_forget()

    def _clear_stats(self):
        for w in self.stats_frame.winfo_children():
            w.destroy()

    def _set_stats(self, rows: list[tuple[str, str]]):
        self._clear_stats()
        for label, value in rows:
            row = ctk.CTkFrame(self.stats_frame, fg_color="transparent")
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(
                row, text=label, font=CAPTION_FONT, text_color=TEXT_SECONDARY, width=120, anchor="w",
            ).pack(side="left")
            ctk.CTkLabel(
                row, text=value, font=BODY_FONT, text_color=TEXT_PRIMARY, anchor="w",
            ).pack(side="left", padx=(8, 0))


class ScanProgressCard(ElevatedCard):
    """Integrated scan progress — replaces NeonScanHero overlay."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.target_progress = 0.0
        self.display_progress = 0.0
        self.scanned = 0
        self.total = 0
        self.status_text = "Preparing scan..."
        self.scan_start_time = None
        self._on_cancel = None
        self._running = False
        self._after_id = None
        self._cancel_requested = False
        self.indeterminate = False
        self._flash_active = False
        self._flash_callback = None

        ctk.CTkLabel(self.body, text="Scanning…", font=SECTION_FONT, text_color=TEXT_PRIMARY).pack(
            anchor="w",
        )
        self.status_label = ctk.CTkLabel(
            self.body, text="", font=BODY_FONT, text_color=TEXT_SECONDARY, wraplength=360, justify="left",
        )
        self.status_label.pack(anchor="w", pady=(CONTROL_GAP, SECTION_GAP))

        self.progress_canvas = tk.Canvas(
            self.body, height=12, bg=SURFACE_BG, highlightthickness=0, bd=0,
        )
        self.progress_canvas.pack(fill="x", pady=(0, CONTROL_GAP))
        self.progress_canvas.bind("<Configure>", lambda _e: self._paint_bar())

        self.count_label = ctk.CTkLabel(
            self.body, text="0 files checked", font=BODY_FONT, text_color=TEXT_PRIMARY,
        )
        self.count_label.pack(anchor="w")
        self.eta_label = ctk.CTkLabel(
            self.body, text="", font=CAPTION_FONT, text_color=TEXT_SECONDARY,
        )
        self.eta_label.pack(anchor="w", pady=(4, SECTION_GAP))

        self.cancel_btn = SecondaryButton(self.body, text="Cancel Scan", command=self._handle_cancel)
        self.cancel_btn.pack(anchor="w")
        self.grid_remove()

    def show(self, on_cancel=None):
        self.target_progress = 0.0
        self.display_progress = 0.0
        self.scanned = 0
        self.total = 0
        self.status_text = "Initializing scan..."
        self._cancel_requested = False
        self._on_cancel = on_cancel
        self._running = True
        self.indeterminate = True
        self.scan_start_time = time.time()
        self.cancel_btn.configure(state="normal", text="Cancel Scan")
        self.grid()
        self._animate()

    def hide(self):
        self._running = False
        if self._after_id is not None:
            self.after_cancel(self._after_id)
            self._after_id = None
        self.grid_remove()

    def _handle_cancel(self):
        if self._cancel_requested:
            return
        self._cancel_requested = True
        self.indeterminate = False
        self.cancel_btn.configure(state="disabled", text="Cancelling…")
        if self._on_cancel:
            self._on_cancel()

    def set_progress(
        self, progress, scanned=None, total=None, status=None, current_file=None,
        duplicate_groups=None, duplicate_files=None, candidates=None,
    ):
        del current_file, duplicate_groups, duplicate_files, candidates
        if scanned is not None:
            self.scanned = scanned
        if total is not None:
            self.total = total
        clamped = max(0.0, min(1.0, progress))
        if self.total == 0 and self.scanned > 0 and not self._cancel_requested:
            clamped = max(clamped, min(0.08, 0.01 + self.scanned / 200_000))
        if self._running and not self._cancel_requested and not self._flash_active:
            clamped = max(self.target_progress, clamped)
        self.target_progress = clamped
        if self._cancel_requested:
            self.indeterminate = False
        else:
            self.indeterminate = self.total == 0 and self.scanned == 0 and self.target_progress < 0.99
        if status:
            self.status_text = status
        self.status_label.configure(text=self.status_text)
        if self.total > 0:
            self.count_label.configure(text=f"{self.scanned:,} of {self.total:,} files checked")
        else:
            self.count_label.configure(text=f"{self.scanned:,} files checked")
        self._update_eta()
        self._paint_bar()

    def flash_complete(self, callback=None, duplicate_groups: int = 0):
        self.indeterminate = False
        self.target_progress = 1.0
        self.display_progress = 1.0
        if duplicate_groups > 0:
            self.status_text = f"Scan complete — {duplicate_groups:,} duplicate group(s) found!"
        else:
            self.status_text = "Scan complete — no duplicates found"
        self.status_label.configure(text=self.status_text)
        self._flash_active = True
        self._flash_callback = callback
        self._paint_bar()
        if callback:
            self.after(700, self._finish_flash)

    def _finish_flash(self):
        self._flash_active = False
        cb = self._flash_callback
        self._flash_callback = None
        if cb:
            cb()

    def _update_eta(self):
        if not self.scan_start_time or self.scanned <= 0 or self.total <= 0:
            self.eta_label.configure(text="Estimating time remaining…")
            return
        elapsed = time.time() - self.scan_start_time
        rate = self.scanned / max(elapsed, 0.1)
        remaining = max(0, self.total - self.scanned)
        secs = int(remaining / max(rate, 0.01))
        mins, s = divmod(secs, 60)
        self.eta_label.configure(text=f"Estimated time remaining: {mins:02d}:{s:02d}")

    def _animate(self):
        if not self._running:
            return
        if not self._flash_active:
            if self.indeterminate:
                if self.scan_start_time:
                    elapsed = time.time() - self.scan_start_time
                    creep = min(0.05, 0.005 + elapsed / 120.0)
                else:
                    creep = 0.005
                self.display_progress = max(self.display_progress, creep)
            else:
                delta = self.target_progress - self.display_progress
                if self._cancel_requested:
                    self.display_progress = self.target_progress
                elif abs(delta) > 0.001:
                    self.display_progress += delta * 0.18
                else:
                    self.display_progress = self.target_progress
        self._paint_bar()
        self._after_id = self.after(50, self._animate)

    def _paint_bar(self):
        c = self.progress_canvas
        c.delete("all")
        w = max(c.winfo_width(), 40)
        h = 12
        cy = h // 2
        c.create_line(4, cy, w - 4, cy, fill=BORDER, width=3, capstyle=tk.ROUND)
        prog = self.display_progress if self._running else self.target_progress
        fill_w = 4 + prog * max(0, w - 8)
        if fill_w > 4:
            c.create_line(4, cy, fill_w, cy, fill=ACCENT, width=3, capstyle=tk.ROUND)
