"""
SQLite FTS5 index for full-text search over PDFs and images (optional Tesseract OCR).
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

INDEX_DIR = Path(os.environ.get("APPDATA", os.path.expanduser("~"))) / "PhotoOrganizer"
INDEX_DB_PATH = INDEX_DIR / "ocr_index.db"

OCR_IMAGE_EXTENSIONS = frozenset({
    ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".webp", ".bmp", ".gif",
})
OCR_DOC_EXTENSIONS = frozenset({".pdf"}) | OCR_IMAGE_EXTENSIONS

try:
    import pytesseract
    from PIL import Image as PILImage

    HAS_PYTESSERACT = True
except ImportError:
    HAS_PYTESSERACT = False
    PILImage = None  # type: ignore

try:
    from pypdf import PdfReader

    HAS_PYPDF = True
except ImportError:
    try:
        from PyPDF2 import PdfReader  # type: ignore

        HAS_PYPDF = True
    except ImportError:
        HAS_PYPDF = False

try:
    from pdfminer.high_level import extract_text as pdfminer_extract_text

    HAS_PDFMINER = True
except ImportError:
    HAS_PDFMINER = False


def index_db_path() -> Path:
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    return INDEX_DB_PATH


def tesseract_available() -> bool:
    if not HAS_PYTESSERACT:
        return False
    return shutil.which("tesseract") is not None


def pdf_extract_available() -> bool:
    return HAS_PYPDF or HAS_PDFMINER


def is_indexable(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in OCR_DOC_EXTENSIONS


def capability_hint() -> str:
    parts: list[str] = []
    if pdf_extract_available():
        lib = "pypdf" if HAS_PYPDF else "pdfminer"
        parts.append(f"PDF text via {lib}")
    else:
        parts.append("PDF: install pypdf or pdfminer.six")
    if tesseract_available():
        parts.append("image OCR via Tesseract")
    elif HAS_PYTESSERACT:
        parts.append("image OCR: install Tesseract binary")
    else:
        parts.append("image OCR: pip install pytesseract + Tesseract")
    return " · ".join(parts)


def _connect() -> sqlite3.Connection:
    path = index_db_path()
    conn = sqlite3.connect(str(path), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS ocr_fts USING fts5(
            filepath UNINDEXED,
            content,
            tokenize='porter unicode61'
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ocr_meta (
            filepath TEXT PRIMARY KEY,
            mtime REAL NOT NULL,
            indexed_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_metadata (
            filepath TEXT PRIMARY KEY,
            ai_tags TEXT NOT NULL DEFAULT '',
            ai_caption TEXT NOT NULL DEFAULT '',
            updated_at REAL NOT NULL
        )
        """
    )
    conn.commit()


def save_ai_metadata(path: str, tags: list[str], caption: str = "") -> None:
    with _connect() as conn:
        ensure_schema(conn)
        conn.execute(
            """
            INSERT INTO ai_metadata (filepath, ai_tags, ai_caption, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(filepath) DO UPDATE SET
                ai_tags = excluded.ai_tags,
                ai_caption = excluded.ai_caption,
                updated_at = excluded.updated_at
            """,
            (path, ",".join(tags), caption, time.time()),
        )
        conn.commit()


def get_ai_tags(path: str) -> list[str]:
    with _connect() as conn:
        ensure_schema(conn)
        row = conn.execute(
            "SELECT ai_tags FROM ai_metadata WHERE filepath = ?", (path,),
        ).fetchone()
        if not row or not row[0]:
            return []
        return [t.strip() for t in str(row[0]).split(",") if t.strip()]


def get_ai_caption(path: str) -> str:
    with _connect() as conn:
        ensure_schema(conn)
        row = conn.execute(
            "SELECT ai_caption FROM ai_metadata WHERE filepath = ?", (path,),
        ).fetchone()
        return str(row[0]) if row and row[0] else ""


def index_exists() -> bool:
    path = index_db_path()
    if not path.is_file():
        return False
    try:
        with _connect() as conn:
            ensure_schema(conn)
            row = conn.execute("SELECT COUNT(*) FROM ocr_meta").fetchone()
            return bool(row and row[0] > 0)
    except sqlite3.Error:
        return False


def index_stats() -> dict[str, int | str]:
    try:
        with _connect() as conn:
            ensure_schema(conn)
            count = conn.execute("SELECT COUNT(*) FROM ocr_meta").fetchone()
            return {
                "documents": int(count[0]) if count else 0,
                "hint": capability_hint(),
            }
    except sqlite3.Error as exc:
        logger.debug("index_stats failed: %s", exc)
        return {"documents": 0, "hint": capability_hint()}


def _sanitize_fts_query(query: str) -> str:
    """Escape FTS5 special chars; wrap tokens for substring-style match."""
    tokens = re.findall(r"[\w]+", query, flags=re.UNICODE)
    if not tokens:
        return ""
    return " OR ".join(f'"{t}"' for t in tokens[:20])


def search_index(query: str) -> set[str]:
    q = _sanitize_fts_query(query.strip())
    if not q or not index_exists():
        return set()
    try:
        with _connect() as conn:
            ensure_schema(conn)
            rows = conn.execute(
                "SELECT filepath FROM ocr_fts WHERE content MATCH ?",
                (q,),
            ).fetchall()
            return {r[0] for r in rows}
    except sqlite3.Error as exc:
        logger.debug("OCR search failed: %s", exc)
        return set()


def _extract_pdf_text(path: str) -> str:
    if HAS_PYPDF:
        try:
            reader = PdfReader(path)
            chunks: list[str] = []
            for page in reader.pages:
                text = page.extract_text() or ""
                if text.strip():
                    chunks.append(text)
            return "\n".join(chunks).strip()
        except Exception as exc:
            logger.debug("pypdf extract failed for %s: %s", path, exc)
    if HAS_PDFMINER:
        try:
            return (pdfminer_extract_text(path) or "").strip()
        except Exception as exc:
            logger.debug("pdfminer extract failed for %s: %s", path, exc)
    return ""


def _extract_image_text(path: str) -> str:
    if not tesseract_available() or not HAS_PYTESSERACT or PILImage is None:
        return ""
    try:
        with PILImage.open(path) as img:
            return (pytesseract.image_to_string(img) or "").strip()
    except Exception as exc:
        logger.debug("OCR failed for %s: %s", path, exc)
        return ""


def extract_document_text(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return _extract_pdf_text(path)
    if ext in OCR_IMAGE_EXTENSIONS:
        return _extract_image_text(path)
    return ""


def _needs_reindex(conn: sqlite3.Connection, path: str) -> bool:
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return False
    row = conn.execute(
        "SELECT mtime FROM ocr_meta WHERE filepath = ?",
        (path,),
    ).fetchone()
    return row is None or float(row[0]) < mtime


def _upsert_document(conn: sqlite3.Connection, path: str, text: str, mtime: float) -> None:
    conn.execute("DELETE FROM ocr_fts WHERE filepath = ?", (path,))
    conn.execute(
        "INSERT INTO ocr_fts (filepath, content) VALUES (?, ?)",
        (path, text or ""),
    )
    conn.execute(
        """
        INSERT INTO ocr_meta (filepath, mtime, indexed_at) VALUES (?, ?, ?)
        ON CONFLICT(filepath) DO UPDATE SET mtime=excluded.mtime, indexed_at=excluded.indexed_at
        """,
        (path, mtime, time.time()),
    )


@dataclass
class BuildIndexResult:
    indexed: int = 0
    skipped: int = 0
    failed: int = 0
    total: int = 0


def list_indexable_files(folder: str, recursive: bool = False) -> list[str]:
    paths: list[str] = []
    if recursive:
        for root, _, files in os.walk(folder):
            for name in sorted(files):
                full = os.path.join(root, name)
                if os.path.isfile(full) and is_indexable(full):
                    paths.append(full)
    else:
        for name in sorted(os.listdir(folder)):
            full = os.path.join(folder, name)
            if os.path.isfile(full) and is_indexable(full):
                paths.append(full)
    return paths


def build_index(
    folder: str,
    recursive: bool = False,
    on_progress: Optional[Callable[[int, int, str], None]] = None,
) -> BuildIndexResult:
    files = list_indexable_files(folder, recursive)
    result = BuildIndexResult(total=len(files))
    if not files:
        return result

    with _connect() as conn:
        ensure_schema(conn)
        indexed_paths: list[str] = []
        for i, path in enumerate(files, start=1):
            if on_progress:
                on_progress(i, len(files), path)
            if not _needs_reindex(conn, path):
                result.skipped += 1
                indexed_paths.append(path)
                continue
            try:
                mtime = os.path.getmtime(path)
            except OSError:
                result.failed += 1
                continue
            text = extract_document_text(path)
            if not text:
                result.skipped += 1
                continue
            try:
                _upsert_document(conn, path, text, mtime)
                indexed_paths.append(path)
                result.indexed += 1
            except sqlite3.Error:
                result.failed += 1
        # Drop index rows for files removed from disk
        rows = conn.execute("SELECT filepath FROM ocr_meta").fetchall()
        valid = set(indexed_paths)
        for (fp,) in rows:
            if fp not in valid and not os.path.isfile(fp):
                conn.execute("DELETE FROM ocr_fts WHERE filepath = ?", (fp,))
                conn.execute("DELETE FROM ocr_meta WHERE filepath = ?", (fp,))
        conn.commit()
    return result
