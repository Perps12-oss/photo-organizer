"""
Safe file access helpers for cloud-synced folders (Yandex.Disk, OneDrive, etc.).
"""
from __future__ import annotations

import logging
import os
from typing import Iterator, Optional

logger = logging.getLogger(__name__)

# Folders that rarely contain user originals worth hashing
SKIP_DIR_NAMES = frozenset({
    ".thumbnails", ".thumbdata", ".thumb", ".cache", ".tmp", ".temp",
    ".Statuses", ".sync", ".git", "__MACOSX",
})

# Windows FILE_ATTRIBUTE_* flags for cloud "online only" placeholders
_WIN_OFFLINE = 0x00001000
_WIN_RECALL_ON_DATA_ACCESS = 0x00400000
_WIN_REPARSE_POINT = 0x00000400


def normalize_filepath(path: str) -> str:
    """Canonical path for Windows (fixes mixed / and \\)."""
    return os.path.normpath(os.path.abspath(path))


def should_skip_dir(dirname: str) -> bool:
    name = dirname.lower().strip()
    return name in SKIP_DIR_NAMES or name.startswith(".")


def is_windows_cloud_placeholder(path: str) -> bool:
    """True when Windows marks the file offline / cloud-only (read often fails with EINVAL)."""
    if os.name != "nt":
        return False
    try:
        import ctypes
        attrs = ctypes.windll.kernel32.GetFileAttributesW(path)
        if attrs == 0xFFFFFFFF:
            return False
        return bool(attrs & (_WIN_OFFLINE | _WIN_RECALL_ON_DATA_ACCESS))
    except Exception:
        return False


def unreadable_reason(path: str) -> Optional[str]:
    """
    Return a short reason if the file cannot be read, else None.
    Probes one byte — catches Yandex/OneDrive placeholders that stat() OK but open() EINVAL.
    """
    path = normalize_filepath(path)
    if not os.path.isfile(path):
        return "not a file"
    if is_windows_cloud_placeholder(path):
        return "cloud placeholder (not downloaded locally)"
    try:
        with open(path, "rb") as f:
            f.read(1)
        return None
    except OSError as e:
        if e.errno == 22:
            return "unreadable (cloud sync or invalid path — Errno 22)"
        if e.errno == 13:
            return "permission denied"
        return f"unreadable ({e})"
    except Exception as e:
        return f"unreadable ({e})"


def is_readable_file(path: str) -> bool:
    return unreadable_reason(path) is None


def iter_file_chunks(path: str, chunk_size: int = 65536) -> Iterator[bytes]:
    """Read file in chunks; raises OSError if unreadable."""
    with open(normalize_filepath(path), "rb") as f:
        while chunk := f.read(chunk_size):
            yield chunk
