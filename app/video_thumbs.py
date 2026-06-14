"""
Video thumbnail extraction via ffmpeg (optional dependency).
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import hashlib
from pathlib import Path

logger = logging.getLogger(__name__)

VIDEO_EXTENSIONS = frozenset({
    ".mov", ".mp4", ".avi", ".mkv", ".webm", ".m4v", ".wmv", ".flv",
})

_CACHE_DIR: Path | None = None


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def is_video_file(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in VIDEO_EXTENSIONS


def thumb_cache_dir() -> Path:
    global _CACHE_DIR
    if _CACHE_DIR is None:
        base = Path(os.environ.get("APPDATA", os.path.expanduser("~"))) / "PhotoOrganizer" / "video_thumbs"
        base.mkdir(parents=True, exist_ok=True)
        _CACHE_DIR = base
    return _CACHE_DIR


def _cache_path(video_path: str) -> Path:
    key = hashlib.sha256(os.path.normcase(video_path).encode("utf-8")).hexdigest()[:24]
    mtime = int(os.path.getmtime(video_path)) if os.path.isfile(video_path) else 0
    return thumb_cache_dir() / f"{key}_{mtime}.jpg"


def extract_video_thumbnail(video_path: str, width: int = 320) -> str | None:
    """
    Return path to a JPEG thumbnail for video_path, generating via ffmpeg if needed.
    Returns None if ffmpeg unavailable or extraction fails.
    """
    if not is_video_file(video_path) or not os.path.isfile(video_path):
        return None
    if not ffmpeg_available():
        return None

    out = _cache_path(video_path)
    if out.is_file() and out.stat().st_size > 0:
        return str(out)

    try:
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-ss", "1", "-i", video_path,
            "-frames:v", "1",
            "-vf", f"scale={width}:-1",
            str(out),
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=30)
        if out.is_file():
            return str(out)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        logger.debug("Video thumb failed for %s: %s", video_path, exc)
    return None
