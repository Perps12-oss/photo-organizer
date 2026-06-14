"""
Video duplicate detection — duration + frame fingerprint via ffmpeg/ffprobe.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import shutil
import subprocess
import tempfile
from collections import defaultdict
from typing import Optional

from duplicate_utils import hamming_distance
from video_thumbs import ffmpeg_available, is_video_file

logger = logging.getLogger(__name__)

try:
    import imagehash
    from PIL import Image

    HAS_IMAGEHASH = True
except ImportError:
    HAS_IMAGEHASH = False

_FP_RE = re.compile(r"^d(\d+)_(.+)$")


def ffprobe_duration(path: str) -> Optional[float]:
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
        logger.debug("ffprobe failed for %s: %s", path, exc)
        return None


def _frame_hash_at(path: str, seconds: float) -> Optional[str]:
    if not ffmpeg_available():
        return None
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    tmp.close()
    try:
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-ss", str(max(0.0, seconds)),
            "-i", path, "-frames:v", "1", tmp.name,
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=30)
        if HAS_IMAGEHASH:
            with Image.open(tmp.name) as img:
                return str(imagehash.phash(img))
        with open(tmp.name, "rb") as f:
            data = f.read(65536)
        return hashlib.sha256(data).hexdigest()[:16]
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        logger.debug("frame hash failed for %s: %s", path, exc)
        return None
    finally:
        try:
            os.remove(tmp.name)
        except OSError:
            pass


def video_fingerprint(path: str) -> Optional[str]:
    """Fingerprint for near-duplicate video matching."""
    if not is_video_file(path) or not os.path.isfile(path):
        return None
    try:
        size = os.path.getsize(path)
    except OSError:
        return None
    dur = ffprobe_duration(path)
    if dur is None:
        return f"size_{size}"
    frame_h = _frame_hash_at(path, min(2.0, dur * 0.25))
    if frame_h:
        return f"d{int(dur * 1000)}_{frame_h}"
    return f"d{int(dur * 1000)}_s{size}"


def _parse_fingerprint(fp: str) -> tuple[Optional[int], Optional[str]]:
    m = _FP_RE.match(fp)
    if not m:
        return None, None
    return int(m.group(1)), m.group(2)


def _duration_close(ms_a: int, ms_b: int, tolerance: int) -> bool:
    if tolerance <= 0:
        return ms_a == ms_b
    max_delta = max(2000, tolerance * 500)
    return abs(ms_a - ms_b) <= max_delta


def _frame_close(hash_a: str, hash_b: str, tolerance: int) -> bool:
    if tolerance <= 0:
        return hash_a == hash_b
    if HAS_IMAGEHASH and len(hash_a) >= 8 and len(hash_b) >= 8:
        return hamming_distance(hash_a, hash_b) <= tolerance
    return hash_a == hash_b


def _duration_bucket(ms: int, tolerance: int) -> int:
    step = max(2000, tolerance * 500)
    return ms // step


def cluster_video_fingerprints(
    items: list[tuple[str, str]],
    tolerance: int = 0,
) -> dict[str, list[str]]:
    """Group videos by fingerprint; tolerance clusters near-matches like pHash."""
    parsed: list[tuple[str, int, str]] = []
    size_only: dict[str, list[str]] = {}
    for path, fp in items:
        if not fp:
            continue
        if fp.startswith("size_"):
            size_only.setdefault(fp, []).append(path)
            continue
        dur_ms, frame_h = _parse_fingerprint(fp)
        if dur_ms is not None and frame_h:
            parsed.append((path, dur_ms, frame_h))

    if tolerance <= 0:
        buckets: dict[str, list[str]] = {}
        for path, fp in items:
            if fp and not fp.startswith("size_"):
                buckets.setdefault(fp, []).append(path)
        for fp, paths in size_only.items():
            if len(paths) > 1:
                buckets.setdefault(fp, []).extend(paths)
        return {f"video_{k}": v for k, v in buckets.items() if len(v) > 1}

    n = len(parsed)
    if n == 0:
        return {f"video_{k}": v for k, v in size_only.items() if len(v) > 1}

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

    # Coarse bucketing by duration window + frame-hash prefix before Hamming compare.
    buckets: dict[tuple[int, str], list[int]] = defaultdict(list)
    for i, (_, dur_ms, frame_h) in enumerate(parsed):
        prefix = (frame_h or "")[:4]
        buckets[(_duration_bucket(dur_ms, tolerance), prefix)].append(i)

    seen_pairs: set[tuple[int, int]] = set()
    bucket_keys = list(buckets.keys())
    for key in bucket_keys:
        indices = buckets[key]
        dur_bucket, prefix = key
        neighbor_keys = [
            (dur_bucket, prefix),
            (dur_bucket - 1, prefix),
            (dur_bucket + 1, prefix),
        ]
        neighbor_indices: list[int] = []
        for nk in neighbor_keys:
            neighbor_indices.extend(buckets.get(nk, []))
        neighbor_indices = sorted(set(neighbor_indices))
        for a_idx in range(len(neighbor_indices)):
            for b_idx in range(a_idx + 1, len(neighbor_indices)):
                i, j = neighbor_indices[a_idx], neighbor_indices[b_idx]
                if i > j:
                    i, j = j, i
                if (i, j) in seen_pairs:
                    continue
                seen_pairs.add((i, j))
                _, d1, h1 = parsed[i]
                _, d2, h2 = parsed[j]
                if _duration_close(d1, d2, tolerance) and _frame_close(h1, h2, tolerance):
                    union(i, j)

    by_root: dict[int, list[str]] = {}
    for i, (path, _, _) in enumerate(parsed):
        by_root.setdefault(find(i), []).append(path)

    result: dict[str, list[str]] = {}
    for root, paths in by_root.items():
        if len(paths) > 1:
            rep = parsed[root][2]
            result[f"video_{rep}"] = paths
    for fp, paths in size_only.items():
        if len(paths) > 1:
            result[f"video_{fp}"] = paths
    return result
