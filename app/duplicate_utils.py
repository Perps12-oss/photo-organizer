"""
Duplicate-finder helpers — pHash clustering with tolerance and group filtering.
"""
from __future__ import annotations

import hashlib
import os
import re
from collections import defaultdict
from typing import Optional

try:
    import imagehash
    HAS_IMAGEHASH = True
except ImportError:
    HAS_IMAGEHASH = False

try:
    from pypdf import PdfReader
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False


def hamming_distance(hash_a: str, hash_b: str) -> int:
    if not HAS_IMAGEHASH or not hash_a or not hash_b:
        return 999
    try:
        return imagehash.hex_to_hash(hash_a) - imagehash.hex_to_hash(hash_b)
    except (ValueError, TypeError):
        return 999


def _phash_bands(hash_hex: str, num_bands: int = 4) -> list[str]:
    """LSH bands for Hamming-neighbor search (4 x 4 hex chars on 64-bit hashes)."""
    h = (hash_hex or "").ljust(16, "0")[:16]
    band_len = 16 // num_bands
    return [h[i : i + band_len] for i in range(0, 16, band_len)]


def cluster_phash(paths_hashes: list[tuple[str, str]], tolerance: int) -> dict[str, list[str]]:
    """
    Cluster (path, hash_hex) pairs by Hamming distance.
    Returns dict cluster_key -> paths (only groups with 2+ files).
    """
    valid = [(p, h) for p, h in paths_hashes if h]
    if not valid:
        return {}

    if tolerance <= 0:
        buckets: dict[str, list[str]] = {}
        for path, h in valid:
            buckets.setdefault(h, []).append(path)
        return {f"pHash_{h}": paths for h, paths in buckets.items() if len(paths) > 1}

    n = len(valid)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    # LSH banding: compare only pairs sharing a hash band (avoids O(n²) over full set).
    band_buckets: dict[str, list[int]] = defaultdict(list)
    for i, (_, h) in enumerate(valid):
        for bi, band in enumerate(_phash_bands(h)):
            band_buckets[f"{bi}:{band}"].append(i)

    seen_pairs: set[tuple[int, int]] = set()
    for indices in band_buckets.values():
        for a_idx in range(len(indices)):
            for b_idx in range(a_idx + 1, len(indices)):
                i, j = indices[a_idx], indices[b_idx]
                if i > j:
                    i, j = j, i
                if (i, j) in seen_pairs:
                    continue
                seen_pairs.add((i, j))
                if hamming_distance(valid[i][1], valid[j][1]) <= tolerance:
                    union(i, j)

    by_root: dict[int, list[str]] = {}
    for i, (path, _) in enumerate(valid):
        by_root.setdefault(find(i), []).append(path)

    result: dict[str, list[str]] = {}
    for root, paths in by_root.items():
        if len(paths) > 1:
            rep = valid[root][1]
            result[f"pHash_{rep}"] = paths
    return result


def find_similar_paths(
    target_hash: str,
    library: list[tuple[str, str]],
    tolerance: int,
    limit: int = 48,
) -> list[tuple[str, int]]:
    """Library-wide similar-image browse: (path, distance) sorted by distance."""
    if not target_hash or tolerance < 0:
        return []
    scored: list[tuple[str, int]] = []
    for path, h in library:
        if not h:
            continue
        dist = hamming_distance(target_hash, h)
        if dist <= tolerance:
            scored.append((path, dist))
    scored.sort(key=lambda x: x[1])
    return scored[:limit]


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _simhash64(text: str) -> str:
    """Simple 64-bit simhash fingerprint for document similarity."""
    tokens = re.findall(r"[a-z0-9]{3,}", _normalize_text(text))
    if not tokens:
        return ""
    vec = [0] * 64
    for token in tokens:
        digest = hashlib.md5(token.encode("utf-8", errors="ignore")).hexdigest()
        value = int(digest[:16], 16)
        for bit in range(64):
            vec[bit] += 1 if (value >> bit) & 1 else -1
    bits = "".join("1" if v >= 0 else "0" for v in vec)
    return f"{int(bits, 2):016x}"


def extract_document_text(path: str, max_chars: int = 120_000) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".txt":
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                return f.read(max_chars)
        except OSError:
            return ""
    if ext == ".pdf" and HAS_PYPDF:
        try:
            reader = PdfReader(path)
            chunks: list[str] = []
            for page in reader.pages[:40]:
                chunks.append(page.extract_text() or "")
                if sum(len(c) for c in chunks) >= max_chars:
                    break
            return "\n".join(chunks)[:max_chars]
        except Exception:
            return ""
    return ""


def document_text_fingerprint(path: str) -> Optional[str]:
    text = extract_document_text(path)
    if len(text.strip()) < 40:
        return None
    return _simhash64(text)


def cluster_document_simhash(
    items: list[tuple[str, str]],
    tolerance: int = 3,
) -> dict[str, list[str]]:
    """Cluster text documents by simhash Hamming distance."""
    valid = [(p, h) for p, h in items if h]
    if not valid:
        return {}
    if tolerance <= 0:
        buckets: dict[str, list[str]] = {}
        for path, h in valid:
            buckets.setdefault(h, []).append(path)
        return {f"doc_{h}": paths for h, paths in buckets.items() if len(paths) > 1}

    n = len(valid)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    band_buckets: dict[str, list[int]] = defaultdict(list)
    for i, (_, h) in enumerate(valid):
        for bi, band in enumerate(_phash_bands(h)):
            band_buckets[f"{bi}:{band}"].append(i)

    seen_pairs: set[tuple[int, int]] = set()
    for indices in band_buckets.values():
        for a_idx in range(len(indices)):
            for b_idx in range(a_idx + 1, len(indices)):
                i, j = indices[a_idx], indices[b_idx]
                if i > j:
                    i, j = j, i
                if (i, j) in seen_pairs:
                    continue
                seen_pairs.add((i, j))
                if hamming_distance(valid[i][1], valid[j][1]) <= tolerance:
                    union(i, j)

    by_root: dict[int, list[str]] = {}
    for i, (path, _) in enumerate(valid):
        by_root.setdefault(find(i), []).append(path)

    result: dict[str, list[str]] = {}
    for root, paths in by_root.items():
        if len(paths) > 1:
            rep = valid[root][1]
            result[f"doc_{rep}"] = paths
    return result


def _file_size(path: str) -> int:
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def _file_mtime(path: str) -> float:
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


def is_similar_group(hash_key: str) -> bool:
    return hash_key.startswith("pHash_") or hash_key.startswith("video_")


def filter_duplicate_groups(
    groups: dict[str, list[str]],
    *,
    group_type: str = "all",
    min_size: int = 2,
    path_contains: str = "",
    min_size_kb: int = 0,
    max_size_kb: int = 0,
    sort_by: str = "count_desc",
) -> list[tuple[str, list[str]]]:
    """Filter and sort duplicate groups for sidebar display."""
    needle = (path_contains or "").strip().lower()
    min_bytes = min_size_kb * 1024 if min_size_kb > 0 else 0
    max_bytes = max_size_kb * 1024 if max_size_kb > 0 else 0

    items: list[tuple[str, list[str]]] = []
    for key, paths in groups.items():
        if len(paths) < max(2, min_size):
            continue
        if group_type == "exact" and (is_similar_group(key) or key.startswith("video_")):
            continue
        if group_type == "similar" and not key.startswith("pHash_"):
            continue
        if group_type == "video" and not key.startswith("video_"):
            continue
        if needle and not any(needle in p.lower() for p in paths):
            continue
        if min_bytes or max_bytes:
            sizes = [_file_size(p) for p in paths]
            if min_bytes and max(sizes) < min_bytes:
                continue
            if max_bytes and min(sizes) > max_bytes:
                continue
        items.append((key, paths))

    if sort_by == "count_asc":
        items.sort(key=lambda x: len(x[1]))
    elif sort_by == "newest":
        items.sort(key=lambda x: max(_file_mtime(p) for p in x[1]), reverse=True)
    elif sort_by == "oldest":
        items.sort(key=lambda x: min(_file_mtime(p) for p in x[1]))
    elif sort_by == "size_desc":
        items.sort(key=lambda x: max(_file_size(p) for p in x[1]), reverse=True)
    else:
        items.sort(key=lambda x: len(x[1]), reverse=True)

    return items
