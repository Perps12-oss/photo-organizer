"""
Audio duplicate fingerprinting — duration + size bucket stub; chromaprint if available.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)

AUDIO_EXTENSIONS = frozenset({".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".wma"})

try:
    import acoustid  # type: ignore[import-untyped]

    HAS_ACOUSTID = True
except ImportError:
    HAS_ACOUSTID = False


def is_audio_file(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in AUDIO_EXTENSIONS


def _ffprobe_duration(path: str) -> Optional[float]:
    if not shutil.which("ffprobe"):
        return None
    try:
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", path,
        ]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=20, check=True)
        return float(out.stdout.strip())
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError, OSError) as exc:
        logger.debug("audio ffprobe failed for %s: %s", path, exc)
        return None


def audio_fingerprint(path: str) -> Optional[str]:
    """Fingerprint for near-duplicate audio matching."""
    if not is_audio_file(path) or not os.path.isfile(path):
        return None
    try:
        size = os.path.getsize(path)
    except OSError:
        return None

    if HAS_ACOUSTID:
        try:
            duration, fp = acoustid.fingerprint_file(path)
            if fp:
                return f"ac_{int(duration * 1000)}_{fp[:16]}"
        except Exception as exc:
            logger.debug("chromaprint failed for %s: %s", path, exc)

    dur = _ffprobe_duration(path)
    if dur is not None:
        bucket = int(dur * 10)
        size_bucket = size // 4096
        return f"dur_{bucket}_sz_{size_bucket}"
    return f"size_{size // 4096}"
