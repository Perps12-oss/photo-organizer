"""
Google Photos Takeout JSON metadata import.
"""
from __future__ import annotations

import datetime
import json
import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)


def is_google_takeout_json(data: dict) -> bool:
    return isinstance(data, dict) and (
        "photoTakenTime" in data or "creationTime" in data or "geoData" in data
    )


def _timestamp_obj(obj: Any) -> Optional[datetime.datetime]:
    if not isinstance(obj, dict):
        return None
    ts = obj.get("timestamp")
    if ts is not None:
        try:
            return datetime.datetime.fromtimestamp(int(ts))
        except (TypeError, ValueError, OSError):
            pass
    formatted = obj.get("formatted")
    if isinstance(formatted, str):
        for fmt in ("%b %d, %Y, %I:%M:%S %p UTC", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.datetime.strptime(formatted, fmt)
            except ValueError:
                continue
    return None


def parse_takeout_fields(data: dict) -> dict[str, Any]:
    """Map Takeout JSON to sidecar-like fields for merge."""
    flat = dict(data)
    for key in ("metadata", "meta"):
        nested = data.get(key)
        if isinstance(nested, dict):
            flat.update(nested)

    title = flat.get("title") or flat.get("name") or ""
    description = flat.get("description") or ""

    dt = _timestamp_obj(flat.get("photoTakenTime")) or _timestamp_obj(flat.get("creationTime"))

    geo = flat.get("geoData") or flat.get("geoDataExif") or {}
    lat = geo.get("latitude")
    lon = geo.get("longitude")

    keywords = []
    if title and title not in description:
        keywords.append(str(title).strip())

    return {
        "caption": description or title,
        "title": title,
        "date_taken": dt,
        "latitude": lat,
        "longitude": lon,
        "keywords": keywords,
        "source": "google_takeout",
    }


def find_takeout_sidecar(image_path: str) -> Optional[str]:
    """Google Takeout supplemental metadata JSON next to image."""
    base, _ = os.path.splitext(image_path)
    candidates = (
        base + ".supplemental-metadata.json",
        image_path + ".supplemental-metadata.json",
        base + ".json",
    )
    for path in candidates:
        if not os.path.isfile(path):
            continue
        try:
            data = json.loads(open(path, encoding="utf-8").read())
            if is_google_takeout_json(data):
                return path
        except (json.JSONDecodeError, OSError):
            continue
    return None


def load_takeout_for_image(image_path: str) -> tuple[Optional[dict], Optional[str]]:
    path = find_takeout_sidecar(image_path)
    if not path:
        return None, None
    try:
        data = json.loads(open(path, encoding="utf-8").read())
        if not is_google_takeout_json(data):
            return None, "Not a Google Takeout JSON file"
        return parse_takeout_fields(data), None
    except (json.JSONDecodeError, OSError) as exc:
        return None, str(exc)


def discover_takeout_albums(takeout_root: str) -> list[dict[str, Any]]:
    """
    Scan a Google Takeout extract for album folders (Takeout/Google Photos/*).
    Returns list of {name, path, image_count, sidecar_count}.
    """
    albums: list[dict[str, Any]] = []
    if not takeout_root or not os.path.isdir(takeout_root):
        return albums

    candidates = [takeout_root]
    for name in ("Google Photos", "Photos", "Takeout/Google Photos"):
        nested = os.path.join(takeout_root, name.replace("/", os.sep))
        if os.path.isdir(nested):
            candidates.append(nested)

    seen: set[str] = set()
    for root in candidates:
        for dirpath, dirnames, filenames in os.walk(root):
            rel = os.path.relpath(dirpath, takeout_root)
            if rel == ".":
                for sub in list(dirnames):
                    sub_path = os.path.join(dirpath, sub)
                    if sub_path in seen:
                        continue
                    seen.add(sub_path)
                    images = [
                        f for f in os.listdir(sub_path)
                        if os.path.splitext(f)[1].lower() in {".jpg", ".jpeg", ".png", ".heic", ".webp", ".gif"}
                    ]
                    if not images:
                        continue
                    sidecars = sum(1 for img in images if find_takeout_sidecar(os.path.join(sub_path, img)))
                    albums.append({
                        "name": sub,
                        "path": sub_path,
                        "image_count": len(images),
                        "sidecar_count": sidecars,
                    })
                break
    return sorted(albums, key=lambda a: a["name"].lower())


def import_takeout_album(album_path: str, merge_sidecars: bool = True) -> tuple[int, int, list[str]]:
    """Merge Takeout sidecars for all images in an album folder. Returns (found, merged, errors)."""
    if not os.path.isdir(album_path):
        return 0, 0, ["Album folder not found"]
    from metadata_tools import merge_sidecar_into_image, list_images

    found = 0
    merged = 0
    errors: list[str] = []
    for path in list_images(album_path, recursive=False):
        sidecar = find_takeout_sidecar(path)
        if not sidecar:
            continue
        found += 1
        if not merge_sidecars:
            continue
        ok, msg = merge_sidecar_into_image(path, sidecar, delete_sidecar=False)
        if ok:
            merged += 1
        else:
            errors.append(f"{os.path.basename(path)}: {msg}")
    return found, merged, errors
