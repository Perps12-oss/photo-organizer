"""
Fast partial + full file hashing for duplicate detection.
Uses xxhash when available (see requirements.txt).
"""
from __future__ import annotations

import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

from file_utils import iter_file_chunks, normalize_filepath

logger = logging.getLogger(__name__)

try:
    import xxhash
    HAS_XXHASH = True
except ImportError:
    HAS_XXHASH = False

QUICK_HASH_BYTES = 1024 * 1024  # first 1 MB — enough to distinguish most files
HASH_CHUNK = 65536


def quick_hash(filepath: str, bytes_to_read: int = QUICK_HASH_BYTES) -> Optional[str]:
    """Hash only the first N bytes — ~100x less I/O than a full read on large files."""
    path = normalize_filepath(filepath)
    try:
        with open(path, "rb") as f:
            chunk = f.read(bytes_to_read)
        if not chunk:
            return None
        if HAS_XXHASH:
            return xxhash.xxh64(chunk).hexdigest()
        return hashlib.md5(chunk, usedforsecurity=False).hexdigest()
    except OSError as e:
        if e.errno != 22:
            logger.debug("quick_hash failed for %s: %s", path, e)
        return None
    except Exception as e:
        logger.debug("quick_hash failed for %s: %s", path, e)
        return None


def full_hash(filepath: str) -> Optional[str]:
    """Full-file hash — only for quick-hash collision groups."""
    path = normalize_filepath(filepath)
    try:
        hasher = xxhash.xxh64() if HAS_XXHASH else hashlib.md5(usedforsecurity=False)
        for chunk in iter_file_chunks(path, HASH_CHUNK):
            hasher.update(chunk)
        return hasher.hexdigest()
    except OSError as e:
        if e.errno != 22:
            logger.debug("full_hash failed for %s: %s", path, e)
        return None
    except Exception as e:
        logger.debug("full_hash failed for %s: %s", path, e)
        return None


def hash_many_parallel(
    file_list: list[str],
    hash_fn: Callable[[str], Optional[str]],
    max_workers: int = 8,
    on_progress: Optional[Callable[[int, int, str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> dict[str, str]:
    """Return {filepath: hash} for successful hashes."""
    results: dict[str, str] = {}
    total = len(file_list)
    if not total:
        return results
    done = 0
    pool = ThreadPoolExecutor(max_workers=max_workers)
    cancelled = False
    try:
        future_map = {pool.submit(hash_fn, fp): fp for fp in file_list}
        for fut in as_completed(future_map):
            if cancel_check and cancel_check():
                cancelled = True
                for pending in future_map:
                    pending.cancel()
                break
            fp = future_map[fut]
            try:
                digest = fut.result()
            except Exception:
                digest = None
            if digest:
                results[fp] = digest
            done += 1
            if on_progress and (done % 8 == 0 or done == total):
                on_progress(done, total, fp)
    finally:
        if cancelled:
            pool.shutdown(wait=False, cancel_futures=True)
        else:
            pool.shutdown(wait=True)
    return results
