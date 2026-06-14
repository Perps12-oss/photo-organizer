"""
Read/write image metadata (EXIF) and bulk rename by event + date.
"""
import datetime
import json
import logging
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, Optional

from app_settings import DEFAULT_SIDECAR_MAPPING, load_sidecar_mapping

from PIL import Image

try:
    import piexif
    HAS_PIEXIF = True
except ImportError:
    HAS_PIEXIF = False

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".webp"}
VIDEO_EXTENSIONS = {
    ".mov", ".mp4", ".avi", ".mkv", ".webm", ".m4v", ".wmv", ".flv",
}
GALLERY_MEDIA_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
WRITABLE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".tif"}

EVENT_KEYWORD_PREFIX = "event:"
RENAME_PATTERN = re.compile(r"^(\d{8})_([^_]+)_(\d{3})(\.[^.]+)$", re.IGNORECASE)
FILENAME_DATE_PREFIX = re.compile(r"^(\d{4})(\d{2})(\d{2})")
FOLDER_EVENT_PATTERN = re.compile(r"^\d{4}-\d{2}_(.+)$", re.IGNORECASE)

# Windows-compatible star rating EXIF tags
RATING_PERCENT_MAP = {0: 0, 1: 1, 2: 25, 3: 50, 4: 75, 5: 99}


@dataclass
class ImageMetadata:
    filepath: str
    filename: str
    date_taken: Optional[datetime.datetime] = None
    caption: str = ""
    keywords: list[str] = field(default_factory=list)
    event: str = ""
    rating: int = 0
    width: int = 0
    height: int = 0
    camera: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    writable: bool = True
    sources: dict[str, str] = field(default_factory=dict)

    @property
    def has_embedded_metadata(self) -> bool:
        return any(v == "exif" for v in self.sources.values())


def is_image_file(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in IMAGE_EXTENSIONS


def is_gallery_media(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in GALLERY_MEDIA_EXTENSIONS


def list_images(folder: str, recursive: bool = False) -> list[str]:
    paths = []
    if recursive:
        for root, _, files in os.walk(folder):
            for name in sorted(files):
                full = os.path.join(root, name)
                if is_image_file(full):
                    paths.append(full)
    else:
        for name in sorted(os.listdir(folder)):
            full = os.path.join(folder, name)
            if os.path.isfile(full) and is_image_file(full):
                paths.append(full)
    return paths


def list_gallery_media(folder: str, recursive: bool = False) -> list[str]:
    """Images and videos for the media gallery grid."""
    paths: list[str] = []
    if recursive:
        for root, _, files in os.walk(folder):
            for name in sorted(files):
                full = os.path.join(root, name)
                if is_gallery_media(full):
                    paths.append(full)
    else:
        for name in sorted(os.listdir(folder)):
            full = os.path.join(folder, name)
            if os.path.isfile(full) and is_gallery_media(full):
                paths.append(full)
    return paths


def scan_gallery_metadata(folder: str, recursive: bool = False) -> dict[str, ImageMetadata]:
    cache: dict[str, ImageMetadata] = {}
    for path in list_gallery_media(folder, recursive=recursive):
        cache[path] = read_metadata(path)
    return cache


def _decode_exif_str(raw) -> str:
    if raw is None:
        return ""
    if isinstance(raw, tuple):
        raw = bytes(raw)
    if isinstance(raw, bytes):
        if len(raw) >= 2 and raw[1] == 0:
            try:
                return raw.decode("utf-16le").strip("\x00").strip()
            except Exception:
                pass
        try:
            return raw.decode("utf-8").strip("\x00").strip()
        except Exception:
            return raw.decode("latin-1", errors="ignore").strip("\x00").strip()
    return str(raw).strip()


def _encode_exif_str(text: str) -> bytes:
    return text.encode("utf-8")


def _encode_xp_str(text: str) -> bytes:
    return (text + "\x00").encode("utf-16le")


def _parse_exif_datetime(raw: str) -> Optional[datetime.datetime]:
    if not raw:
        return None
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.datetime.strptime(raw.strip(), fmt)
        except ValueError:
            continue
    return None


def _keywords_from_string(text: str) -> list[str]:
    if not text:
        return []
    parts = re.split(r"[,;]", text)
    return [p.strip() for p in parts if p.strip()]


def _event_from_keywords(keywords: list[str]) -> str:
    for kw in keywords:
        if kw.lower().startswith(EVENT_KEYWORD_PREFIX):
            return kw[len(EVENT_KEYWORD_PREFIX):].strip()
    return ""


def _keywords_with_event(keywords: list[str], event: str) -> list[str]:
    cleaned = [k for k in keywords if not k.lower().startswith(EVENT_KEYWORD_PREFIX)]
    if event.strip():
        cleaned.insert(0, f"{EVENT_KEYWORD_PREFIX}{event.strip()}")
    return cleaned


def _clamp_rating(value) -> int:
    try:
        r = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(5, r))


def _read_rating_from_exif(exif_dict: dict) -> int:
    if not HAS_PIEXIF:
        return 0
    raw = exif_dict.get("0th", {}).get(piexif.ImageIFD.Rating)
    if raw is None:
        return 0
    if isinstance(raw, tuple):
        raw = raw[0] if raw else 0
    return _clamp_rating(raw)


def display_tags(keywords: list[str]) -> list[str]:
    """Keywords suitable for filter UI (excludes event: prefix)."""
    return [k for k in keywords if not k.lower().startswith(EVENT_KEYWORD_PREFIX)]


def collect_tags(meta_cache: dict[str, ImageMetadata]) -> list[str]:
    tags: set[str] = set()
    for meta in meta_cache.values():
        tags.update(t.lower() for t in display_tags(meta.keywords))
    return sorted(tags)


def scan_folder_metadata(folder: str, recursive: bool = False) -> dict[str, ImageMetadata]:
    cache: dict[str, ImageMetadata] = {}
    for path in list_images(folder, recursive=recursive):
        cache[path] = read_metadata(path)
    return cache


def filter_files(
    all_files: list[str],
    meta_cache: dict[str, ImageMetadata],
    tags: Optional[list[str]] = None,
    min_rating: int = 0,
    match_all: bool = False,
    search_text: str = "",
    ocr_paths: Optional[set[str]] = None,
    date_from: Optional["datetime.datetime"] = None,
    date_to: Optional["datetime.datetime"] = None,
) -> list[str]:
    tags = [t.strip().lower() for t in (tags or []) if t.strip()]
    search = search_text.strip().lower()
    result = []
    for path in all_files:
        meta = meta_cache.get(path)
        if meta is None:
            meta = read_metadata(path)
            meta_cache[path] = meta
        if meta.rating < min_rating:
            continue
        if date_from or date_to:
            taken = meta.date_taken
            if taken is None:
                continue
            if date_from and taken < date_from:
                continue
            if date_to and taken > date_to:
                continue
        file_tags = [t.lower() for t in display_tags(meta.keywords)]
        if tags:
            if match_all:
                if not all(t in file_tags for t in tags):
                    continue
            else:
                if not any(t in file_tags for t in tags):
                    continue
        if search:
            haystack = " ".join([
                meta.filename.lower(),
                meta.caption.lower(),
                meta.event.lower(),
                " ".join(file_tags),
            ])
            if search not in haystack and not (ocr_paths and path in ocr_paths):
                continue
        result.append(path)
    return result


def parse_event_from_filename(filename: str) -> str:
    match = RENAME_PATTERN.match(filename)
    if match:
        return match.group(2)
    parts = os.path.splitext(filename)[0].split("_")
    if len(parts) >= 2 and len(parts[0]) == 8 and parts[0].isdigit():
        return parts[1]
    return ""


def parse_date_from_filename(filename: str) -> Optional[datetime.datetime]:
    match = RENAME_PATTERN.match(filename)
    if match:
        try:
            return datetime.datetime.strptime(match.group(1), "%Y%m%d")
        except ValueError:
            pass
    prefix = FILENAME_DATE_PREFIX.match(os.path.splitext(filename)[0])
    if prefix:
        try:
            return datetime.datetime(int(prefix.group(1)), int(prefix.group(2)), int(prefix.group(3)))
        except ValueError:
            pass
    return None


def infer_event_from_path(filepath: str) -> str:
    """Infer event name from parent folders like 2026-06_LondonTrip."""
    for part in reversed(os.path.normpath(filepath).split(os.sep)):
        match = FOLDER_EVENT_PATTERN.match(part)
        if match:
            return match.group(1).replace("_", " ").strip()
    return ""


def format_detection_summary(meta: ImageMetadata) -> str:
    if not meta.sources:
        return "No metadata detected in file."
    labels = {
        "date_taken": "Date",
        "caption": "Caption",
        "keywords": "Tags",
        "event": "Event",
        "rating": "Rating",
        "camera": "Camera",
    }
    source_labels = {"exif": "EXIF", "filename": "filename", "folder": "folder", "file_date": "file date"}
    parts = []
    for key, label in labels.items():
        src = meta.sources.get(key)
        if src:
            parts.append(f"{label} ({source_labels.get(src, src)})")
    if meta.camera and "camera" not in meta.sources:
        parts.append("Camera (EXIF)")
    if not parts:
        return "No embedded metadata — check filename or folder naming."
    return "Auto-detected: " + ", ".join(parts)


def _apply_piexif_dict(meta: ImageMetadata, exif_dict: dict):
    desc = exif_dict.get("0th", {}).get(piexif.ImageIFD.ImageDescription)
    if desc:
        if isinstance(desc, tuple):
            desc = bytes(desc)
        text = _decode_exif_str(desc)
        if text:
            meta.caption = text
            meta.sources["caption"] = "exif"
    if not meta.caption:
        comment = exif_dict.get("0th", {}).get(piexif.ImageIFD.XPComment)
        if comment:
            if isinstance(comment, tuple):
                comment = bytes(comment)
            text = _decode_exif_str(comment)
            if text:
                meta.caption = text
                meta.sources["caption"] = "exif"
    for dt_tag in (piexif.ExifIFD.DateTimeOriginal, piexif.ExifIFD.DateTimeDigitized):
        dt_raw = exif_dict.get("Exif", {}).get(dt_tag)
        if dt_raw and not meta.date_taken:
            parsed = _parse_exif_datetime(_decode_exif_str(dt_raw))
            if parsed:
                meta.date_taken = parsed
                meta.sources["date_taken"] = "exif"
    kw_raw = exif_dict.get("0th", {}).get(piexif.ImageIFD.XPKeywords)
    if kw_raw:
        if isinstance(kw_raw, tuple):
            kw_raw = bytes(kw_raw)
        kws = _keywords_from_string(_decode_exif_str(kw_raw))
        if kws:
            meta.keywords = kws
            meta.sources["keywords"] = "exif"
    if not meta.keywords:
        subject = exif_dict.get("0th", {}).get(piexif.ImageIFD.XPSubject)
        if subject:
            if isinstance(subject, tuple):
                subject = bytes(subject)
            kws = _keywords_from_string(_decode_exif_str(subject))
            if kws:
                meta.keywords = kws
                meta.sources["keywords"] = "exif"
    make = exif_dict.get("0th", {}).get(piexif.ImageIFD.Make)
    model = exif_dict.get("0th", {}).get(piexif.ImageIFD.Model)
    if make or model:
        meta.camera = f"{_decode_exif_str(make)} {_decode_exif_str(model)}".strip()
        if meta.camera:
            meta.sources["camera"] = "exif"
    rating = _read_rating_from_exif(exif_dict)
    if rating:
        meta.rating = rating
        meta.sources["rating"] = "exif"
    from gps_utils import gps_from_piexif_dict
    lat, lon = gps_from_piexif_dict(exif_dict)
    if lat is not None and lon is not None:
        meta.latitude = lat
        meta.longitude = lon
        meta.sources["gps"] = "exif"


def _apply_pillow_exif(meta: ImageMetadata, exif) -> bool:
    found = False
    if not exif:
        return found
    if not meta.caption:
        desc = exif.get(270)
        if desc:
            meta.caption = str(desc).strip()
            if meta.caption:
                meta.sources["caption"] = "exif"
                found = True
    if not meta.date_taken:
        for tag in (36867, 36868, 306):
            dt_raw = exif.get(tag)
            if dt_raw:
                parsed = _parse_exif_datetime(str(dt_raw))
                if parsed:
                    meta.date_taken = parsed
                    meta.sources["date_taken"] = "exif"
                    found = True
                    break
    return found


def _apply_filename_and_folder_hints(meta: ImageMetadata, filepath: str):
    fname = os.path.basename(filepath)
    if not meta.event:
        from_name = parse_event_from_filename(fname)
        if from_name:
            meta.event = from_name
            meta.sources["event"] = "filename"
    if not meta.event:
        from_folder = infer_event_from_path(filepath)
        if from_folder:
            meta.event = from_folder
            meta.sources["event"] = "folder"
    if not meta.date_taken or meta.sources.get("date_taken") == "file_date":
        from_name = parse_date_from_filename(fname)
        if from_name:
            meta.date_taken = from_name
            meta.sources["date_taken"] = "filename"
    if not meta.event:
        ev = _event_from_keywords(meta.keywords)
        if ev:
            meta.event = ev
            if "event" not in meta.sources:
                meta.sources["event"] = "exif"


def read_metadata(filepath: str) -> ImageMetadata:
    ext = os.path.splitext(filepath)[1].lower()
    meta = ImageMetadata(
        filepath=filepath,
        filename=os.path.basename(filepath),
        writable=ext in WRITABLE_EXTENSIONS and (HAS_PIEXIF or ext == ".jpg"),
    )
    try:
        with Image.open(filepath) as img:
            meta.width, meta.height = img.size
    except Exception as e:
        logger.warning("Image open failed for %s: %s", filepath, e)

    if HAS_PIEXIF and ext in IMAGE_EXTENSIONS:
        try:
            exif_dict = piexif.load(filepath)
            _apply_piexif_dict(meta, exif_dict)
        except Exception:
            pass

    try:
        with Image.open(filepath) as img:
            exif = img.getexif()
            if exif:
                _apply_pillow_exif(meta, exif)
            if not meta.date_taken:
                exif_data = img.info.get("exif")
                if exif_data and HAS_PIEXIF:
                    try:
                        _apply_piexif_dict(meta, piexif.load(exif_data))
                    except Exception:
                        pass
    except Exception:
        pass

    if not meta.date_taken:
        try:
            meta.date_taken = datetime.datetime.fromtimestamp(os.path.getmtime(filepath))
            meta.sources["date_taken"] = "file_date"
        except OSError:
            pass

    _apply_filename_and_folder_hints(meta, filepath)
    if not meta.event:
        meta.event = _event_from_keywords(meta.keywords)
    if meta.latitude is None:
        from gps_utils import read_gps_from_image
        lat, lon = read_gps_from_image(filepath)
        if lat is not None and lon is not None:
            meta.latitude = lat
            meta.longitude = lon
            meta.sources["gps"] = meta.sources.get("gps", "exif")
    return meta


def write_metadata(
    filepath: str,
    date_taken: Optional[datetime.datetime] = None,
    caption: Optional[str] = None,
    keywords: Optional[list[str]] = None,
    event: Optional[str] = None,
    rating: Optional[int] = None,
) -> tuple[bool, str]:
    ext = os.path.splitext(filepath)[1].lower()
    if ext not in WRITABLE_EXTENSIONS:
        return False, f"Metadata write not supported for {ext} files."

    kw_list = list(keywords or [])
    if event is not None:
        kw_list = _keywords_with_event(kw_list, event)

    if not HAS_PIEXIF:
        return _write_metadata_pillow(filepath, date_taken, caption, kw_list)

    try:
        exif_dict = {}
        try:
            exif_dict = piexif.load(filepath)
        except Exception:
            exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}

        if caption is not None:
            exif_dict.setdefault("0th", {})[piexif.ImageIFD.ImageDescription] = _encode_exif_str(caption)
        if date_taken is not None:
            dt_str = date_taken.strftime("%Y:%m:%d %H:%M:%S").encode("utf-8")
            exif_dict.setdefault("Exif", {})[piexif.ExifIFD.DateTimeOriginal] = dt_str
            exif_dict.setdefault("Exif", {})[piexif.ExifIFD.DateTimeDigitized] = dt_str
            exif_dict.setdefault("0th", {})[piexif.ImageIFD.DateTime] = dt_str
        if keywords is not None or event is not None:
            kw_text = ", ".join(kw_list)
            exif_dict.setdefault("0th", {})[piexif.ImageIFD.XPKeywords] = _encode_xp_str(kw_text)
        if rating is not None:
            stars = _clamp_rating(rating)
            zeroth = exif_dict.setdefault("0th", {})
            if stars == 0:
                zeroth.pop(piexif.ImageIFD.Rating, None)
                zeroth.pop(piexif.ImageIFD.RatingPercent, None)
            else:
                zeroth[piexif.ImageIFD.Rating] = stars
                zeroth[piexif.ImageIFD.RatingPercent] = RATING_PERCENT_MAP[stars]

        exif_bytes = piexif.dump(exif_dict)
        with Image.open(filepath) as img:
            img.save(filepath, exif=exif_bytes)
        return True, "Metadata saved."
    except Exception as e:
        logger.error("Metadata write failed for %s: %s", filepath, e)
        return False, str(e)


def _write_metadata_pillow(
    filepath: str,
    date_taken: Optional[datetime.datetime],
    caption: Optional[str],
    keywords: list[str],
) -> tuple[bool, str]:
    try:
        with Image.open(filepath) as img:
            exif = img.getexif()
            if caption is not None:
                text = caption
                if keywords:
                    text = f"{caption} | tags: {', '.join(keywords)}"
                exif[270] = text
            if date_taken is not None:
                dt_str = date_taken.strftime("%Y:%m:%d %H:%M:%S")
                exif[36867] = dt_str
                exif[306] = dt_str
            img.save(filepath, exif=exif)
        return True, "Metadata saved (basic EXIF)."
    except Exception as e:
        return False, str(e)


def bulk_rename_plan(
    folder: str,
    event_name: str,
    use_exif_date: bool = True,
    recursive: bool = False,
) -> list[tuple[str, str]]:
    """Return list of (old_path, new_path) rename pairs."""
    event_name = re.sub(r"[^\w\-]+", "_", event_name.strip()) or "Event"
    files = list_images(folder, recursive=recursive)
    plan = []
    for idx, src in enumerate(files, start=1):
        ext = os.path.splitext(src)[1].lower()
        if use_exif_date:
            meta = read_metadata(src)
            dt = meta.date_taken or datetime.datetime.now()
        else:
            dt = datetime.datetime.now()
        new_name = f"{dt.strftime('%Y%m%d')}_{event_name}_{idx:03d}{ext}"
        dst = os.path.join(os.path.dirname(src), new_name)
        if os.path.normcase(src) != os.path.normcase(dst):
            dst = _unique_path(dst)
            plan.append((src, dst))
    return plan


def _unique_path(path: str) -> str:
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    n = 1
    while True:
        candidate = f"{base}_{n}{ext}"
        if not os.path.exists(candidate):
            return candidate
        n += 1


def apply_rename_plan(plan: list[tuple[str, str]]) -> tuple[int, list[str]]:
    done = 0
    errors = []
    for src, dst in plan:
        try:
            os.rename(src, dst)
            done += 1
        except OSError as e:
            errors.append(f"{os.path.basename(src)}: {e}")
    return done, errors


def format_rename_preview(plan: list[tuple[str, str]], limit: int = 30) -> str:
    if not plan:
        return "No files to rename."
    lines = [f"{len(plan)} file(s) will be renamed:", ""]
    for src, dst in plan[:limit]:
        lines.append(f"  {os.path.basename(src)}")
        lines.append(f"    -> {os.path.basename(dst)}")
    if len(plan) > limit:
        lines.append(f"  ... and {len(plan) - limit} more")
    return "\n".join(lines)


# --- Sidecar merge (JSON / XMP -> embedded EXIF) ---

SIDECAR_NESTED_KEYS = ("metadata", "meta", "exif", "data", "image", "photo", "xmp")

XMP_NS = {
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "x": "adobe:ns:meta/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "xmp": "http://ns.adobe.com/xap/1.0/",
    "exif": "http://ns.adobe.com/exif/1.0/",
    "tiff": "http://ns.adobe.com/tiff/1.0/",
    "photoshop": "http://ns.adobe.com/photoshop/1.0/",
    "Iptc4xmpCore": "http://iptc.org/std/Iptc4xmpCore/1.0/xmlns/",
}


def sidecar_candidates(image_path: str) -> list[str]:
    """Possible sidecar paths for an image (first match wins)."""
    base, _ = os.path.splitext(image_path)
    folder = os.path.dirname(image_path)
    stem = os.path.basename(base)
    names = (
        stem + ".supplemental-metadata.json",
        stem + ".json",
        stem + ".metadata.json",
        os.path.basename(image_path) + ".supplemental-metadata.json",
        os.path.basename(image_path) + ".json",
        stem + ".meta.json",
        stem + ".xmp",
    )
    seen = set()
    paths = []
    for name in names:
        full = os.path.join(folder, name)
        if full not in seen:
            seen.add(full)
            paths.append(full)
    return paths


def _sidecar_kind(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".xmp":
        return "xmp"
    return "json"


def find_sidecar(image_path: str) -> Optional[str]:
    """Return path to JSON or XMP sidecar, if any."""
    for candidate in sidecar_candidates(image_path):
        if os.path.isfile(candidate):
            return candidate
    return None


def find_sidecar_json(image_path: str) -> Optional[str]:
    """Backward-compatible alias — returns JSON or XMP sidecar."""
    return find_sidecar(image_path)


def _flatten_sidecar_dict(data: dict) -> dict[str, Any]:
    flat = dict(data)
    for key in SIDECAR_NESTED_KEYS:
        nested = data.get(key)
        if isinstance(nested, dict):
            for k, v in nested.items():
                if k not in flat or flat[k] in (None, "", [], {}):
                    flat[k] = v
    return flat


def _sidecar_value(data: dict, *keys: str) -> Any:
    for key in keys:
        if key in data and data[key] not in (None, "", [], {}):
            return data[key]
        for variant in (key, key.lower(), key.upper(), key[0].lower() + key[1:] if key else key):
            if variant in data and data[variant] not in (None, "", [], {}):
                return data[variant]
    return None


def _parse_sidecar_date(value: Any) -> Optional[datetime.datetime]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.datetime.fromtimestamp(value)
        except (OSError, ValueError):
            return None
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            return datetime.datetime.fromisoformat(text)
        except ValueError:
            pass
        for fmt in (
            "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y:%m:%d %H:%M:%S",
            "%Y/%m/%d %H:%M:%S", "%d/%m/%Y %H:%M:%S",
        ):
            try:
                return datetime.datetime.strptime(text, fmt)
            except ValueError:
                continue
    return None


def _parse_sidecar_keywords(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        return _keywords_from_string(value)
    return []


def parse_sidecar_fields(
    data: dict,
    mapping: Optional[dict[str, list[str]]] = None,
) -> dict[str, Any]:
    """Map sidecar keys to write_metadata arguments using configurable field mapping."""
    from takeout_import import is_google_takeout_json, parse_takeout_fields

    flat = _flatten_sidecar_dict(data)
    if is_google_takeout_json(flat):
        tf = parse_takeout_fields(flat)
        fields: dict[str, Any] = {}
        if tf.get("caption"):
            fields["caption"] = tf["caption"]
        if tf.get("keywords"):
            fields["keywords"] = tf["keywords"]
        if tf.get("date_taken"):
            fields["date_taken"] = tf["date_taken"]
        if tf.get("latitude") is not None and tf.get("longitude") is not None:
            fields["latitude"] = tf["latitude"]
            fields["longitude"] = tf["longitude"]
        return fields

    field_map = mapping or load_sidecar_mapping()
    fields: dict[str, Any] = {}

    caption_keys = field_map.get("caption", DEFAULT_SIDECAR_MAPPING["caption"])
    caption = _sidecar_value(flat, *caption_keys)
    if caption is not None:
        fields["caption"] = str(caption).strip()

    event_keys = field_map.get("event", DEFAULT_SIDECAR_MAPPING["event"])
    event = _sidecar_value(flat, *event_keys)
    if event is not None:
        fields["event"] = str(event).strip()

    keyword_keys = field_map.get("keywords", DEFAULT_SIDECAR_MAPPING["keywords"])
    keywords = _sidecar_value(flat, *keyword_keys)
    kw_list = _parse_sidecar_keywords(keywords)
    if kw_list:
        fields["keywords"] = kw_list

    rating_keys = field_map.get("rating", DEFAULT_SIDECAR_MAPPING["rating"])
    rating = _sidecar_value(flat, *rating_keys)
    if rating is not None:
        fields["rating"] = _clamp_rating(rating)

    date_keys = field_map.get("date_taken", DEFAULT_SIDECAR_MAPPING["date_taken"])
    date_raw = _sidecar_value(flat, *date_keys)
    dt = _parse_sidecar_date(date_raw)
    if dt:
        fields["date_taken"] = dt

    return fields


def _load_json_sidecar_raw(sidecar_path: str) -> tuple[Optional[dict], Optional[str]]:
    try:
        data = json.loads(open(sidecar_path, encoding="utf-8").read())
        if not isinstance(data, dict):
            return None, "Sidecar JSON must be an object"
        return data, None
    except json.JSONDecodeError as exc:
        return None, f"Invalid JSON: {exc}"
    except OSError as exc:
        return None, str(exc)


def load_sidecar_data(sidecar_path: str) -> tuple[Optional[dict], Optional[str]]:
    kind = _sidecar_kind(sidecar_path)
    if kind == "xmp":
        return load_sidecar_xmp(sidecar_path)
    return load_sidecar_json(sidecar_path)


def load_sidecar_json(sidecar_path: str) -> tuple[Optional[dict], Optional[str]]:
    try:
        with open(sidecar_path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as e:
        return None, str(e)
    if not isinstance(data, dict):
        return None, "Sidecar JSON must be an object (not a list or plain value)."
    return data, None


def _xmp_tag_name(tag: str) -> tuple[str, str]:
    if tag.startswith("{"):
        uri, local = tag[1:].split("}", 1)
        for prefix, ns_uri in XMP_NS.items():
            if ns_uri == uri:
                return f"{prefix}:{local}", local
        return local, local
    if ":" in tag:
        return tag, tag.split(":", 1)[1]
    return tag, tag


def _xmp_collect_rdf_values(node: ET.Element) -> list[str]:
    values: list[str] = []
    for child in node:
        local = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if local in ("Bag", "Seq", "Alt"):
            for li in child:
                li_local = li.tag.split("}")[-1] if "}" in li.tag else li.tag
                if li_local == "li":
                    text = (li.text or "").strip()
                    if text:
                        values.append(text)
                    for attr_val in li.attrib.values():
                        text = str(attr_val).strip()
                        if text:
                            values.append(text)
        elif child.text and child.text.strip():
            values.append(child.text.strip())
    if not values and node.text and node.text.strip():
        values.append(node.text.strip())
    return values


def _flatten_xmp_element(elem: ET.Element, flat: dict[str, Any]):
    prefixed, local = _xmp_tag_name(elem.tag)
    if prefixed not in flat:
        children = list(elem)
        if not children:
            text = (elem.text or "").strip()
            if text:
                flat[prefixed] = text
                flat[local] = text
        elif len(children) == 1:
            child_local = children[0].tag.split("}")[-1] if "}" in children[0].tag else children[0].tag
            if child_local in ("Bag", "Seq", "Alt"):
                values = _xmp_collect_rdf_values(elem)
                if values:
                    flat[prefixed] = values if len(values) > 1 else values[0]
                    flat[local] = flat[prefixed]
        else:
            values = _xmp_collect_rdf_values(elem)
            if values:
                flat[prefixed] = values if len(values) > 1 else values[0]
                flat[local] = flat[prefixed]

    for attr_key, attr_val in elem.attrib.items():
        if attr_key in ("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about", "rdf:about"):
            continue
        prefixed, local = _xmp_tag_name(attr_key)
        text = str(attr_val).strip()
        if text:
            flat[prefixed] = text
            flat[local] = text

    for child in elem:
        _flatten_xmp_element(child, flat)


def load_sidecar_xmp(sidecar_path: str) -> tuple[Optional[dict], Optional[str]]:
    try:
        with open(sidecar_path, "rb") as handle:
            content = handle.read()
        root = ET.fromstring(content)
    except (OSError, ET.ParseError) as e:
        return None, str(e)
    flat: dict[str, Any] = {}
    _flatten_xmp_element(root, flat)
    if not flat:
        return None, "XMP sidecar contains no readable metadata."
    return flat, None


def sidecar_preview(sidecar_path: str, mapping: Optional[dict[str, list[str]]] = None) -> str:
    data, err = load_sidecar_data(sidecar_path)
    if err:
        return f"Error reading sidecar: {err}"
    fields = parse_sidecar_fields(data, mapping=mapping)
    if not fields:
        return "Sidecar found but no recognized metadata fields."
    kind = _sidecar_kind(sidecar_path).upper()
    parts = []
    for key, val in fields.items():
        if key == "keywords":
            parts.append(f"tags: {', '.join(val)}")
        elif key == "date_taken" and isinstance(val, datetime.datetime):
            parts.append(f"date: {val.strftime('%Y-%m-%d %H:%M')}")
        else:
            parts.append(f"{key}: {val}")
    return f"{kind} sidecar -> " + ", ".join(parts)


def merge_sidecar_into_image(
    image_path: str,
    sidecar_path: Optional[str] = None,
    delete_sidecar: bool = False,
    mapping: Optional[dict[str, list[str]]] = None,
) -> tuple[bool, str]:
    """Embed JSON/XMP sidecar metadata into the image EXIF. Optionally remove the sidecar file."""
    sidecar = sidecar_path or find_sidecar(image_path)
    if not sidecar:
        return False, "No JSON or XMP sidecar found for this image."
    data, err = load_sidecar_data(sidecar)
    if err:
        return False, f"Could not read sidecar: {err}"
    fields = parse_sidecar_fields(data, mapping=mapping)
    if not fields:
        return False, "Sidecar has no recognized metadata fields to merge."
    ok, msg = write_metadata(image_path, **fields)
    if not ok:
        return False, msg
    kind = _sidecar_kind(sidecar).upper()
    result = f"Merged {kind} metadata from {os.path.basename(sidecar)} into {os.path.basename(image_path)}."
    if delete_sidecar:
        try:
            os.remove(sidecar)
            result += f" Deleted {os.path.basename(sidecar)}."
        except OSError as e:
            result += f" (Could not delete sidecar: {e})"
    return True, result


def find_sidecar_pairs(folder: str, recursive: bool = False) -> list[tuple[str, str]]:
    pairs = []
    for image_path in list_images(folder, recursive=recursive):
        sidecar = find_sidecar(image_path)
        if sidecar:
            pairs.append((image_path, sidecar))
    return pairs


def merge_sidecar_pairs(
    pairs: list[tuple[str, str]],
    delete_sidecar: bool = False,
    mapping: Optional[dict[str, list[str]]] = None,
) -> tuple[int, int, list[str]]:
    """Merge an explicit list of (image, sidecar) pairs. Returns (merged, failed, errors)."""
    merged = 0
    errors = []
    for image_path, sidecar_path in pairs:
        ok, msg = merge_sidecar_into_image(
            image_path, sidecar_path, delete_sidecar=delete_sidecar, mapping=mapping,
        )
        if ok:
            merged += 1
        else:
            errors.append(f"{os.path.basename(image_path)}: {msg}")
    failed = len(pairs) - merged
    return merged, failed, errors


def merge_all_sidecars(
    folder: str,
    recursive: bool = False,
    delete_sidecar: bool = False,
    mapping: Optional[dict[str, list[str]]] = None,
) -> tuple[int, int, list[str]]:
    """Returns (merged_count, skipped_count, error_messages)."""
    pairs = find_sidecar_pairs(folder, recursive=recursive)
    merged = 0
    errors = []
    for image_path, sidecar_path in pairs:
        ok, msg = merge_sidecar_into_image(
            image_path, sidecar_path, delete_sidecar=delete_sidecar, mapping=mapping,
        )
        if ok:
            merged += 1
        else:
            errors.append(f"{os.path.basename(image_path)}: {msg}")
    skipped = len(pairs) - merged
    return merged, skipped, errors


# --- Metadata export ---

EXPORT_CSV_COLUMNS = (
    "filepath", "filename", "date_taken", "caption", "event", "rating",
    "keywords", "width", "height", "camera", "latitude", "longitude", "sources",
)


def metadata_to_dict(meta: ImageMetadata) -> dict:
    return {
        "filepath": meta.filepath,
        "filename": meta.filename,
        "date_taken": meta.date_taken.isoformat(sep=" ") if meta.date_taken else "",
        "caption": meta.caption,
        "event": meta.event,
        "rating": meta.rating,
        "keywords": list(meta.keywords),
        "width": meta.width,
        "height": meta.height,
        "camera": meta.camera,
        "latitude": meta.latitude if meta.latitude is not None else "",
        "longitude": meta.longitude if meta.longitude is not None else "",
        "sources": dict(meta.sources),
    }


def export_metadata_json(metas: list[ImageMetadata], path: str) -> int:
    import json as _json
    payload = [metadata_to_dict(m) for m in metas]
    with open(path, "w", encoding="utf-8") as f:
        _json.dump(payload, f, indent=2, ensure_ascii=False)
    return len(payload)


def export_metadata_csv(metas: list[ImageMetadata], path: str) -> int:
    import csv
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=EXPORT_CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for meta in metas:
            row = metadata_to_dict(meta)
            row["keywords"] = "; ".join(meta.keywords)
            row["sources"] = "; ".join(f"{k}={v}" for k, v in meta.sources.items())
            writer.writerow(row)
    return len(metas)


def batch_autodetect_plan(paths: list[str]) -> list[tuple[str, ImageMetadata, list[str]]]:
    """
    For each path, read metadata and list fields that would be filled from hints only.
    Returns (path, meta, fields_to_apply) where fields are caption/event/keywords/date_taken/rating.
    """
    results = []
    for path in paths:
        meta = read_metadata(path)
        to_apply = []
        if meta.event and meta.sources.get("event") != "exif":
            to_apply.append("event")
        if meta.caption and meta.sources.get("caption") != "exif":
            to_apply.append("caption")
        if meta.keywords and not meta.has_embedded_metadata:
            to_apply.append("keywords")
        if meta.date_taken and meta.sources.get("date_taken") in ("filename", "folder", "file_date"):
            to_apply.append("date_taken")
        if to_apply:
            results.append((path, meta, to_apply))
    return results


def apply_autodetected_metadata(path: str, meta: ImageMetadata, fields: list[str]) -> tuple[bool, str]:
    """Write autodetected fields back to file EXIF."""
    kwargs = {}
    if "caption" in fields:
        kwargs["caption"] = meta.caption
    if "event" in fields:
        kwargs["event"] = meta.event
    if "keywords" in fields:
        kwargs["keywords"] = meta.keywords
    if "date_taken" in fields:
        kwargs["date_taken"] = meta.date_taken
    if "rating" in fields:
        kwargs["rating"] = meta.rating
    if not kwargs:
        return True, "nothing to apply"
    ok, msg = write_metadata(path, **kwargs)
    return ok, msg
