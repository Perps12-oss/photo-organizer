"""
In-app image viewers — embedded panel and fullscreen lightbox.
"""
from __future__ import annotations

import os
from typing import Callable, Optional

import customtkinter as ctk
from PIL import Image, ImageOps

from design_system import SecondaryButton
from metadata_tools import ImageMetadata, read_metadata
from theme import (
    BORDER, CARD_RADIUS, FONT_MONO_SM, INPUT_BG, SURFACE_BG, TEXT_PRIMARY, TEXT_SECONDARY, WINDOW_BG,
)
from video_player import InlineVideoPlayer
from video_thumbs import extract_video_thumbnail, is_video_file


def load_oriented_image(path: str) -> Image.Image:
    with Image.open(path) as img:
        return ImageOps.exif_transpose(img)


def load_preview_image(path: str) -> Image.Image:
    """Load an image or video frame thumbnail for gallery preview."""
    if is_video_file(path):
        thumb = extract_video_thumbnail(path)
        if thumb:
            with Image.open(thumb) as img:
                return img.copy()
        raise OSError("video preview unavailable")
    return load_oriented_image(path)


def fit_image(img: Image.Image, max_w: int, max_h: int) -> Image.Image:
    if max_w < 1 or max_h < 1:
        return img
    copy = img.copy()
    copy.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
    return copy


def pil_to_ctk_image(pil_img: Image.Image) -> ctk.CTkImage:
    size = pil_img.size
    return ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=size)


def rating_stars_text(rating: int) -> str:
    rating = max(0, min(5, rating))
    return ("*" * rating) + ("." * (5 - rating))


class EmbeddedImageViewer(ctk.CTkFrame):
    """Fit-to-panel preview with overlay info."""

    def __init__(self, parent, on_fullscreen: Optional[Callable[[], None]] = None, **kwargs):
        super().__init__(parent, fg_color=INPUT_BG, corner_radius=8, **kwargs)
        self.on_fullscreen = on_fullscreen
        self._photo = None
        self._current_path: Optional[str] = None
        self._meta: Optional[ImageMetadata] = None
        self._resize_after_id = None

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.canvas_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.canvas_frame.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self.canvas_frame.grid_rowconfigure(0, weight=1)
        self.canvas_frame.grid_columnconfigure(0, weight=1)

        self.image_label = ctk.CTkLabel(self.canvas_frame, text="No image", text_color=TEXT_SECONDARY)
        self.image_label.grid(row=0, column=0, sticky="nsew")

        self.info_label = ctk.CTkLabel(
            self, text="", font=FONT_MONO_SM, text_color=TEXT_SECONDARY, anchor="w", justify="left",
        )
        self.info_label.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 4))

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 8))
        if on_fullscreen:
            SecondaryButton(btn_row, text="Fullscreen", width=100, command=on_fullscreen).pack(side="left")
        self.play_video_btn = SecondaryButton(
            btn_row, text="▶ Play video", width=100, command=self._play_video_inline,
        )
        self.play_video_btn.pack(side="left", padx=(8, 0))
        self.play_video_btn.pack_forget()
        self._video_player: Optional[InlineVideoPlayer] = None

        self.bind("<Configure>", self._on_resize)
        self.canvas_frame.bind("<Configure>", self._on_resize)

    def show_image(self, path: Optional[str], meta: Optional[ImageMetadata] = None):
        self._stop_video()
        self._current_path = path
        if not path or not os.path.isfile(path):
            self._photo = None
            self._meta = None
            self.image_label.configure(image=None, text="No image")
            self.info_label.configure(text="")
            self.play_video_btn.pack_forget()
            return
        self._meta = meta or read_metadata(path)
        if is_video_file(path):
            self.play_video_btn.pack(side="left", padx=(8, 0))
        else:
            self.play_video_btn.pack_forget()
        self._refresh_image()
        self._update_info()

    def _stop_video(self):
        if self._video_player:
            self._video_player.stop()
            self._video_player.grid_remove()

    def _play_video_inline(self):
        if not self._current_path or not is_video_file(self._current_path):
            return
        self._stop_video()
        if self._video_player is None:
            self._video_player = InlineVideoPlayer(self.canvas_frame)
            self._video_player.grid(row=0, column=0, sticky="nsew")
        self.image_label.grid_remove()
        self._video_player.grid()
        if self._video_player.load(self._current_path):
            self._video_player.play()

    def _update_info(self):
        if not self._meta:
            self.info_label.configure(text="")
            return
        m = self._meta
        date_s = m.date_taken.strftime("%Y-%m-%d %H:%M") if m.date_taken else "—"
        tags = ", ".join(k for k in m.keywords if not k.lower().startswith("event:")) or "—"
        kind = " (video)" if self._current_path and is_video_file(self._current_path) else ""
        self.info_label.configure(
            text=f"{m.filename}{kind}  |  {rating_stars_text(m.rating)}  |  {date_s}\nTags: {tags}"
        )

    def _on_resize(self, _event=None):
        if not self._current_path:
            return
        if self._resize_after_id:
            self.after_cancel(self._resize_after_id)
        self._resize_after_id = self.after(120, self._refresh_image)

    def _refresh_image(self):
        self._resize_after_id = None
        if not self._current_path:
            return
        if self._video_player and self._video_player.winfo_ismapped():
            return
        self.image_label.grid()
        try:
            w = max(200, self.canvas_frame.winfo_width() - 8)
            h = max(200, self.canvas_frame.winfo_height() - 8)
            img = load_preview_image(self._current_path)
            fitted = fit_image(img, w, h)
            img.close()
            self._photo = pil_to_ctk_image(fitted)
            self.image_label.configure(image=self._photo, text="")
        except Exception:
            if is_video_file(self._current_path):
                self.image_label.configure(image=None, text="Video — install ffmpeg for preview")
            else:
                self.image_label.configure(image=None, text="Preview unavailable")

    def get_current_path(self) -> Optional[str]:
        return self._current_path


class LightboxViewer(ctk.CTkToplevel):
    """Fullscreen image viewer with keyboard navigation."""

    _VIEWER_ACTIONS = (
        "viewer_close", "viewer_prev", "viewer_next", "viewer_toggle_video", "viewer_save",
        "viewer_rating_0", "viewer_rating_1", "viewer_rating_2",
        "viewer_rating_3", "viewer_rating_4", "viewer_rating_5",
    )

    def __init__(
        self,
        parent,
        files: list[str],
        start_index: int = 0,
        meta_cache: Optional[dict[str, ImageMetadata]] = None,
        on_rating_change: Optional[Callable[[str, int], None]] = None,
        on_save: Optional[Callable[[str], None]] = None,
        shortcut_manager=None,
        metadata_provider=None,
    ):
        super().__init__(parent)
        self.files = files
        self.index = max(0, min(start_index, len(files) - 1)) if files else 0
        self.meta_cache = meta_cache or {}
        self.on_rating_change = on_rating_change
        self.on_save = on_save
        self._shortcut_manager = shortcut_manager
        self._metadata_provider = metadata_provider
        self._photo = None
        self._video_player: Optional[InlineVideoPlayer] = None
        self._key_bindings: list = []

        self.title("Media Viewer")
        self.configure(fg_color=WINDOW_BG)
        self.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0")
        self.attributes("-fullscreen", True)
        self._fade_supported = True
        try:
            self.attributes("-alpha", 0.0)
        except Exception:
            self._fade_supported = False

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.content = ctk.CTkFrame(self, fg_color=WINDOW_BG)
        self.content.grid(row=0, column=0, sticky="nsew")
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        self.image_label = ctk.CTkLabel(self.content, text="", fg_color=WINDOW_BG)
        self.image_label.grid(row=0, column=0, sticky="nsew")

        self._bind_viewer_keys()
        self.bind("<Configure>", lambda e: self._show_current())
        self.focus_set()

        if files:
            self._show_current()
        else:
            self.image_label.configure(text="No images", text_color=TEXT_SECONDARY)
        self._fade_in()

        self.hud = ctk.CTkFrame(
            self, fg_color=SURFACE_BG, corner_radius=CARD_RADIUS, border_width=1, border_color=BORDER,
        )
        self.hud.place(relx=0.5, rely=0.97, anchor="s")
        self.hud_label = ctk.CTkLabel(
            self.hud, text="", font=FONT_MONO_SM, text_color=TEXT_PRIMARY,
            padx=16, pady=8,
        )
        self.hud_label.pack()

    def _bind_viewer_keys(self):
        sm = self._shortcut_manager
        if sm:
            bindings = {
                "viewer_close": (lambda e: self._close(), "<Escape>"),
                "viewer_prev": (lambda e: self._nav(-1), "<Left>"),
                "viewer_next": (lambda e: self._nav(1), "<Right>"),
                "viewer_toggle_video": (lambda e: self._toggle_video(), "<space>"),
                "viewer_save": (lambda e: self._save_current(), "<Control-s>"),
            }
            for i in range(6):
                bindings[f"viewer_rating_{i}"] = (
                    lambda e, n=i: self._set_rating(n), f"<Key-{i}>",
                )
            for action, (handler, default) in bindings.items():
                sm.bind(self, action, default, handler)
            return
        keys = {
            "<Escape>": lambda e: self._close(),
            "<Left>": lambda e: self._nav(-1),
            "<Right>": lambda e: self._nav(1),
            "<space>": lambda e: self._toggle_video(),
            "<Control-s>": lambda e: self._save_current(),
            "<Control-S>": lambda e: self._save_current(),
        }
        for i in range(6):
            keys[f"<Key-{i}>"] = lambda e, n=i: self._set_rating(n)
        for seq, handler in keys.items():
            self.bind(seq, handler, add="+")
            self._key_bindings.append((self, seq, handler))

    def _unbind_viewer_keys(self):
        sm = self._shortcut_manager
        if sm:
            sm.unbind_actions(self, list(self._VIEWER_ACTIONS))
            return
        for widget, seq, handler in self._key_bindings:
            try:
                widget.unbind(seq, handler)
            except Exception:
                pass
        self._key_bindings.clear()

    def _close(self):
        self._unbind_viewer_keys()
        self._stop_video()
        self.destroy()

    def _stop_video(self):
        if self._video_player:
            self._video_player.stop()
            self._video_player.destroy()
            self._video_player = None

    def _toggle_video(self):
        path = self._current_path()
        if path and is_video_file(path) and self._video_player:
            self._video_player.toggle_play()

    def _fade_in(self, step: float = 0.0):
        if not self._fade_supported:
            return
        step += 0.12
        try:
            self.attributes("-alpha", min(1.0, step))
        except Exception:
            self._fade_supported = False
            return
        if step < 1.0:
            self.after(20, lambda: self._fade_in(step))

    def _nav(self, delta: int):
        if not self.files:
            return
        self.index = (self.index + delta) % len(self.files)
        self._show_current()

    def _current_path(self) -> Optional[str]:
        if not self.files:
            return None
        return self.files[self.index]

    def _get_meta(self, path: str) -> ImageMetadata:
        if path in self.meta_cache:
            return self.meta_cache[path]
        if self._metadata_provider is not None:
            meta = self._metadata_provider.peek(path)
            if meta is None:
                meta = self._metadata_provider.get_sync(path)
            self.meta_cache[path] = meta
            return meta
        meta = read_metadata(path)
        self.meta_cache[path] = meta
        return meta

    def _set_rating(self, rating: int):
        path = self._current_path()
        if not path:
            return
        meta = self._get_meta(path)
        meta.rating = max(0, min(5, rating))
        if self.on_rating_change:
            self.on_rating_change(path, meta.rating)
        self._update_hud(meta)

    def _save_current(self):
        path = self._current_path()
        if path and self.on_save:
            self.on_save(path)

    def _update_hud(self, meta: ImageMetadata):
        pos = f"{self.index + 1}/{len(self.files)}" if self.files else "0/0"
        date_s = meta.date_taken.strftime("%Y-%m-%d") if meta.date_taken else "—"
        video_hint = "  Space play/pause" if self._current_path() and is_video_file(self._current_path() or "") else ""
        self.hud_label.configure(
            text=f"{pos}  {meta.filename}  |  {rating_stars_text(meta.rating)}  |  {date_s}  "
                 f"|  Esc close  <- -> nav  0-5 rate  Ctrl+S save{video_hint}"
        )

    def _show_current(self):
        path = self._current_path()
        if not path:
            return
        self._stop_video()
        meta = self._get_meta(path)
        if is_video_file(path):
            self.image_label.grid_remove()
            self._video_player = InlineVideoPlayer(self.content)
            self._video_player.grid(row=0, column=0, sticky="nsew")
            if self._video_player.load(path):
                self._video_player.play()
            self._update_hud(meta)
            return
        self.image_label.grid()
        try:
            w = max(400, self.winfo_width() - 40)
            h = max(300, self.winfo_height() - 80)
            img = load_preview_image(path)
            fitted = fit_image(img, w, h)
            img.close()
            self._photo = pil_to_ctk_image(fitted)
            self.image_label.configure(image=self._photo, text="")
        except Exception:
            if is_video_file(path):
                self.image_label.configure(
                    image=None, text="Video preview unavailable (ffmpeg required)",
                    text_color=TEXT_SECONDARY,
                )
            else:
                self.image_label.configure(
                    image=None, text="Cannot display image", text_color=TEXT_SECONDARY,
                )
        self._update_hud(meta)


class SideBySideCompareDialog(ctk.CTkToplevel):
    """Compare two images side by side in the gallery."""

    def __init__(self, parent, path_a: str, path_b: str):
        super().__init__(parent)
        self.title("Side-by-side compare")
        self.geometry("960x520")
        self.configure(fg_color=WINDOW_BG)
        self.transient(parent)

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="both", expand=True, padx=12, pady=(12, 0))
        row.grid_columnconfigure(0, weight=1)
        row.grid_columnconfigure(1, weight=1)
        row.grid_rowconfigure(0, weight=1)

        self._refs: list[ctk.CTkImage] = []
        for col, path in enumerate((path_a, path_b)):
            panel = ctk.CTkFrame(row, fg_color=INPUT_BG, corner_radius=8)
            panel.grid(row=0, column=col, sticky="nsew", padx=6)
            ctk.CTkLabel(
                panel, text=os.path.basename(path), font=FONT_MONO_SM, text_color=TEXT_SECONDARY,
            ).pack(pady=(8, 4))
            img_label = ctk.CTkLabel(panel, text="")
            img_label.pack(expand=True, padx=8, pady=8)
            try:
                img = load_preview_image(path)
                fitted = fit_image(img, 420, 380)
                img.close()
                ctk_img = pil_to_ctk_image(fitted)
                self._refs.append(ctk_img)
                img_label.configure(image=ctk_img, text="")
            except OSError:
                img_label.configure(text="Preview unavailable", text_color=TEXT_SECONDARY)

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=12, pady=12)
        SecondaryButton(footer, text="Close", width=90, command=self.destroy).pack(side="right")
