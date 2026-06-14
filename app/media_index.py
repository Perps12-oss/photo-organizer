"""
SQLite media index for fast folder listing on large libraries (100k+ files).
"""
from __future__ import annotations

import logging
import os
import sqlite3
import time
from pathlib import Path
from typing import Callable, Optional

from metadata_tools import GALLERY_MEDIA_EXTENSIONS, is_gallery_media
from video_thumbs import is_video_file

logger = logging.getLogger(__name__)

INDEX_DIR = Path(os.environ.get("APPDATA", os.path.expanduser("~"))) / "PhotoOrganizer"
INDEX_DB = INDEX_DIR / "media_index.db"


def _connect() -> sqlite3.Connection:
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(INDEX_DB), timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS media_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            root_folder TEXT NOT NULL,
            filepath TEXT NOT NULL UNIQUE,
            filename TEXT NOT NULL,
            extension TEXT,
            size INTEGER NOT NULL DEFAULT 0,
            mtime REAL NOT NULL DEFAULT 0,
            media_type TEXT NOT NULL DEFAULT 'image',
            indexed_at REAL NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_media_root ON media_files(root_folder)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_media_mtime ON media_files(mtime)")
    conn.commit()


def index_stats() -> dict[str, int]:
    try:
        with _connect() as conn:
            ensure_schema(conn)
            row = conn.execute("SELECT COUNT(*) AS c FROM media_files").fetchone()
            roots = conn.execute("SELECT COUNT(DISTINCT root_folder) AS c FROM media_files").fetchone()
            return {
                "files": int(row["c"]) if row else 0,
                "roots": int(roots["c"]) if roots else 0,
            }
    except sqlite3.Error:
        return {"files": 0, "roots": 0}


def _norm_root(folder: str) -> str:
    return os.path.normcase(os.path.abspath(folder))


def sync_folder(
    folder: str,
    recursive: bool = False,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> int:
    """Walk folder and upsert into index. Returns number of files indexed."""
    root = _norm_root(folder)
    if not os.path.isdir(folder):
        return 0
    now = time.time()
    seen: set[str] = set()
    batch: list[tuple] = []

    def flush(conn: sqlite3.Connection) -> None:
        if not batch:
            return
        conn.executemany(
            """
            INSERT INTO media_files (root_folder, filepath, filename, extension, size, mtime, media_type, indexed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(filepath) DO UPDATE SET
                size=excluded.size, mtime=excluded.mtime, media_type=excluded.media_type, indexed_at=excluded.indexed_at
            """,
            batch,
        )
        batch.clear()

    count = 0
    with _connect() as conn:
        ensure_schema(conn)
        if recursive:
            walker = os.walk(folder)
            for dirpath, _, files in walker:
                for name in files:
                    full = os.path.join(dirpath, name)
                    if not is_gallery_media(full):
                        continue
                    try:
                        st = os.stat(full)
                    except OSError:
                        continue
                    seen.add(os.path.normcase(os.path.abspath(full)))
                    ext = os.path.splitext(name)[1].lower()
                    batch.append((
                        root,
                        os.path.abspath(full),
                        name,
                        ext,
                        st.st_size,
                        st.st_mtime,
                        "video" if is_video_file(full) else "image",
                        now,
                    ))
                    count += 1
                    if on_progress and count % 500 == 0:
                        on_progress(count, 0)
                    if len(batch) >= 200:
                        flush(conn)
        else:
            for name in sorted(os.listdir(folder)):
                full = os.path.join(folder, name)
                if not os.path.isfile(full) or not is_gallery_media(full):
                    continue
                try:
                    st = os.stat(full)
                except OSError:
                    continue
                seen.add(os.path.normcase(os.path.abspath(full)))
                ext = os.path.splitext(name)[1].lower()
                batch.append((
                    root,
                    os.path.abspath(full),
                    name,
                    ext,
                    st.st_size,
                    st.st_mtime,
                    "video" if is_video_file(full) else "image",
                    now,
                ))
                count += 1
        flush(conn)
        # Remove stale rows for this root
        rows = conn.execute(
            "SELECT filepath FROM media_files WHERE root_folder = ?",
            (root,),
        ).fetchall()
        for row in rows:
            fp = row["filepath"]
            if os.path.normcase(fp) not in seen:
                conn.execute("DELETE FROM media_files WHERE filepath = ?", (fp,))
        conn.commit()
    return count


def list_from_index(folder: str, recursive: bool = False) -> list[str]:
    """Return file paths from index for folder; empty if not indexed."""
    root = _norm_root(folder)
    root_abs = os.path.abspath(folder)
    try:
        with _connect() as conn:
            ensure_schema(conn)
            rows = conn.execute(
                "SELECT filepath FROM media_files WHERE root_folder = ? ORDER BY filepath",
                (root,),
            ).fetchall()
            result: list[str] = []
            for row in rows:
                fp = row["filepath"]
                if not os.path.isfile(fp):
                    continue
                if recursive:
                    if fp == root_abs or fp.startswith(root_abs + os.sep):
                        result.append(fp)
                else:
                    if os.path.normcase(os.path.dirname(fp)) == os.path.normcase(root_abs):
                        result.append(fp)
            return result
    except sqlite3.Error as exc:
        logger.debug("list_from_index failed: %s", exc)
        return []


def sync_and_list(
    folder: str,
    recursive: bool = False,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> list[str]:
    """Sync folder to index then return paths (falls back to walk if index empty)."""
    from metadata_tools import list_gallery_media

    sync_folder(folder, recursive=recursive, on_progress=on_progress)
    paths = list_from_index(folder, recursive=recursive)
    if paths:
        return paths
    return list_gallery_media(folder, recursive=recursive)
