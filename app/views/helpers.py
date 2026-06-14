"""Shared helpers for Photo Organizer views."""
import logging
import math
import os
import time

import cv2
from PIL import Image

try:
    import imagehash
    HAS_IMAGEHASH = True
except ImportError:
    HAS_IMAGEHASH = False
    logging.warning("imagehash not available. Install with: pip install imagehash")

IMAGE_EXTENSIONS = frozenset({
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp", ".heic", ".heif",
})

def is_image_file(filepath: str) -> bool:
    return os.path.splitext(filepath)[1].lower() in IMAGE_EXTENSIONS


def calculate_fast_score(filepath):
    """Lightweight score without loading pixels — used during scan."""
    score = 0
    try:
        size_mb = os.path.getsize(filepath) / (1024 * 1024)
        score += min(size_mb, 50) * 2
        mtime = os.path.getmtime(filepath)
        days_old = (time.time() - mtime) / 86400
        score += max(0, (365 - days_old) / 365) * 30
        fname = os.path.basename(filepath).lower()
        if any(k in fname for k in ("edit", "final", "enhanced", "processed", "best")):
            score += 15
        if any(k in fname for k in ("copy", "duplicate", "backup", "copy of")):
            score -= 10
        if "screenshot" in fname:
            score -= 20
        if any(k in fname for k in ("img_", "dsc", "pict", "photo_")):
            score += 5
    except Exception as e:
        logging.debug("Fast score failed for %s: %s", filepath, e)
    return round(score, 2)


def calculate_image_score(filepath, use_cv2: bool = True):
    """
    Unified scoring: higher = better to keep.

    Worker-thread only: uses cv2.imread and may block on large images.
    Never call from the Tk main/UI thread.
    """
    score = 0
    try:
        if not use_cv2 or not is_image_file(filepath):
            return calculate_fast_score(filepath)
        # 1. Technical Quality (40% weight)
        img = cv2.imread(filepath)
        if img is not None:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
            score += sharpness * 0.4  # Sharpness score
            
            # 2. Resolution & Size (30% weight)
            height, width = img.shape[:2]
            file_size_mb = os.path.getsize(filepath) / (1024*1024)
            score += ((width * height) / 1_000_000) * 0.2  # Megapixels
            score += min(file_size_mb, 50) * 0.1  # Size bonus, capped at 50MB
        
        # 3. Temporal & Origin (30% weight)
        mtime = os.path.getmtime(filepath)
        days_old = (time.time() - mtime) / 86400
        score += max(0, (365 - days_old) / 365) * 30  # Newer is better
        
        # 4. Filename Heuristics (Bonus/Penalty)
        fname = os.path.basename(filepath).lower()
        if any(keyword in fname for keyword in ['edit', 'final', 'enhanced', 'processed', 'best']):
            score += 15  # Bonus for edited versions
        if any(keyword in fname for keyword in ['copy', 'duplicate', 'backup', 'copy of']):
            score -= 10  # Penalty for obvious copies
        if 'screenshot' in fname:
            score -= 20  # Screenshots often lower priority
        if any(keyword in fname for keyword in ['img_', 'dsc', 'pict', 'photo_']):
            score += 5  # Likely camera originals
            
    except Exception as e:
        logging.error(f"Scoring failed for {filepath}: {e}")
    return round(score, 2)

def get_score_color(score):
    """Get color based on score (red=bad, green=good)."""
    if score > 70:
        return "#198754"  # Green
    elif score > 40:
        return "#ffc107"  # Yellow
    else:
        return "#dc3545"  # Red

def calculate_perceptual_hash(image_path):
    """Calculate perceptual hash for similar image detection."""
    if not HAS_IMAGEHASH:
        return None
    try:
        img = Image.open(image_path)
        return str(imagehash.average_hash(img))
    except Exception as e:
        logging.error(f"Perceptual hash failed for {image_path}: {e}")
        return None


def truncate_middle(text, max_len=52):
    if len(text) <= max_len:
        return text
    keep = (max_len - 3) // 2
    return text[:keep] + "..." + text[-keep:]


def format_eta(seconds):
    if seconds is None or seconds < 0 or math.isinf(seconds):
        return "--:--"
    minutes, secs = divmod(int(seconds), 60)
    if minutes >= 60:
        hours, minutes = divmod(minutes, 60)
        return f"{hours}h {minutes}m"
    return f"{minutes}:{secs:02d}"


def format_elapsed(seconds):
    """Human-readable elapsed time for scan timer."""
    if seconds is None or seconds < 0:
        return "0:00"
    total = int(seconds)
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours > 0:
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    return f"{minutes}:{secs:02d}"


def count_duplicate_stats(hash_map: dict[str, list[str]]) -> tuple[int, int]:
    """Return (group_count, file_count) for hash buckets with 2+ files."""
    groups = [paths for paths in hash_map.values() if len(paths) > 1]
    return len(groups), sum(len(paths) for paths in groups)

