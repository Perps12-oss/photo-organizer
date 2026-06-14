"""
Inline video playback using OpenCV (optional — falls back to thumbnail).
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import customtkinter as ctk
from PIL import Image

from video_thumbs import extract_video_thumbnail, is_video_file

logger = logging.getLogger(__name__)

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False
    cv2 = None  # type: ignore

APP_TEXT_MUTED = "#8899aa"


def cv2_available() -> bool:
    return HAS_CV2


class InlineVideoPlayer(ctk.CTkFrame):
    """Play/pause video with scrub bar in a CTk frame."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color="#0f0f18", **kwargs)
        self._path: Optional[str] = None
        self._cap = None
        self._playing = False
        self._after_id: Optional[str] = None
        self._fps = 24.0
        self._frame_count = 0
        self._speed = 1.0
        self._photo = None

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.display = ctk.CTkLabel(self, text="", fg_color="#000000")
        self.display.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)

        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))
        controls.grid_columnconfigure(1, weight=1)

        self.play_btn = ctk.CTkButton(controls, text="▶ Play", width=80, command=self.toggle_play)
        self.play_btn.grid(row=0, column=0, padx=(0, 8))
        self.scrub = ctk.CTkSlider(controls, from_=0, to=100, command=self._on_scrub)
        self.scrub.grid(row=0, column=1, sticky="ew", padx=4)
        self.speed_menu = ctk.CTkOptionMenu(
            controls, values=["0.5x", "1x", "1.5x", "2x"], width=70, command=self._on_speed,
        )
        self.speed_menu.set("1x")
        self.speed_menu.grid(row=0, column=2, padx=(8, 0))
        self.time_label = ctk.CTkLabel(controls, text="0:00 / 0:00", font=("Consolas", 10), text_color=APP_TEXT_MUTED)
        self.time_label.grid(row=0, column=3, padx=(8, 0))

        self.bind("<Destroy>", lambda _e: self.stop())

    def load(self, path: str) -> bool:
        self.stop()
        self._path = path
        if not is_video_file(path) or not os.path.isfile(path):
            self.display.configure(image=None, text="Not a video file")
            return False
        if not HAS_CV2:
            return self._show_thumb_fallback("OpenCV required for playback (pip install opencv-python)")
        self._cap = cv2.VideoCapture(path)
        if not self._cap.isOpened():
            self._cap = None
            return self._show_thumb_fallback("Cannot open video")
        self._fps = float(self._cap.get(cv2.CAP_PROP_FPS) or 24.0)
        self._frame_count = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        self.scrub.configure(to=max(1, self._frame_count - 1))
        self.scrub.set(0)
        self._show_frame(0)
        self.play_btn.configure(text="▶ Play")
        return True

    def _show_thumb_fallback(self, msg: str) -> bool:
        thumb = extract_video_thumbnail(self._path or "")
        if thumb:
            with Image.open(thumb) as img:
                self._photo = ctk.CTkImage(light_image=img.copy(), dark_image=img.copy(), size=(320, 180))
            self.display.configure(image=self._photo, text="")
            self.time_label.configure(text=msg)
            return True
        self.display.configure(image=None, text=msg, text_color=APP_TEXT_MUTED)
        return False

    def toggle_play(self):
        if self._playing:
            self.pause()
        else:
            self.play()

    def play(self):
        if not self._cap or not HAS_CV2:
            return
        self._playing = True
        self.play_btn.configure(text="⏸ Pause")
        self._tick()

    def pause(self):
        self._playing = False
        self.play_btn.configure(text="▶ Play")
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None

    def stop(self):
        self.pause()
        if self._cap:
            self._cap.release()
            self._cap = None
        self._path = None

    def _on_speed(self, choice: str):
        self._speed = float(choice.replace("x", ""))

    def _on_scrub(self, value: float):
        if not self._cap or not HAS_CV2:
            return
        self._show_frame(int(value))
        if self._playing:
            self.pause()

    def _show_frame(self, frame_idx: int) -> None:
        if not self._cap or not HAS_CV2:
            return
        self._cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, frame_idx))
        ok, frame = self._cap.read()
        if not ok:
            return
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w = rgb.shape[:2]
        max_w = max(400, self.display.winfo_width() or 640)
        max_h = max(300, self.display.winfo_height() or 360)
        scale = min(max_w / w, max_h / h, 1.0)
        if scale < 1.0:
            rgb = cv2.resize(rgb, (int(w * scale), int(h * scale)))
        pil = Image.fromarray(rgb)
        self._photo = ctk.CTkImage(light_image=pil, dark_image=pil, size=pil.size)
        self.display.configure(image=self._photo, text="")
        cur_sec = frame_idx / self._fps if self._fps else 0
        total_sec = self._frame_count / self._fps if self._fps else 0
        self.time_label.configure(text=f"{_fmt_time(cur_sec)} / {_fmt_time(total_sec)}")
        self.scrub.set(frame_idx)

    def _tick(self):
        if not self._playing or not self._cap or not HAS_CV2:
            return
        idx = int(self._cap.get(cv2.CAP_PROP_POS_FRAMES))
        if idx >= self._frame_count - 1:
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            idx = 0
        self._show_frame(idx + 1)
        delay = max(16, int(1000 / (self._fps * self._speed)))
        self._after_id = self.after(delay, self._tick)


def _fmt_time(seconds: float) -> str:
    seconds = max(0, int(seconds))
    m, s = divmod(seconds, 60)
    return f"{m}:{s:02d}"
