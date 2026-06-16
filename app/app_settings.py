"""
App-wide settings (metadata auto-save, sidecar field mapping).

Stored alongside watcher settings in %APPDATA%\\PhotoOrganizer\\
"""

import json
import logging
import os
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from theme import APPEARANCE_MODES, GALLERY_SORT_OPTIONS
from theme_presets import DEFAULT_PRESET_ID, normalize_preset_id

logger = logging.getLogger(__name__)

SETTINGS_DIR = Path(os.environ.get("APPDATA", os.path.expanduser("~"))) / "PhotoOrganizer"
APP_SETTINGS_FILE = SETTINGS_DIR / "app_settings.json"

SCHEMA_VERSION = 1

KNOWN_APP_KEYS = frozenset({
    "schema_version",
    "appearance_mode",
    "auto_save_metadata",
    "auto_save_delay_ms",
    "sidecar_field_mapping",
    "metadata_panel_collapsed",
    "gallery_sort",
    "scan_depth_label",
    "idle_duplicate_scan_enabled",
    "idle_duplicate_scan_folder",
    "idle_duplicate_scan_days",
    "idle_duplicate_scan_idle_minutes",
    "idle_duplicate_scan_cooldown_hours",
    "last_idle_duplicate_scan_at",
    "suppress_config_warnings",
    "suppress_ffmpeg_warning",
    "phash_tolerance",
    "video_duplicate_tolerance",
    "conflict_policy",
    "folder_template",
    "filename_template",
    "ollama_url",
    "enable_local_ai",
    "snapshot_before_delete",
    "use_media_index",
    "recent_scan_folders",
    "auto_ocr_on_folder_load",
    "custom_accent",
    "theme_preset",
    "keyboard_shortcuts",
    "locale",
    "idle_duplicate_scan_cpu_limit",
    "idle_duplicate_scan_skip_on_battery",
    "idle_duplicate_scan_only_when_locked",
})

CONFLICT_POLICIES = ("rename", "skip", "overwrite")

SIDECAR_FIELD_LABELS = {
    "caption": "Caption / description",
    "event": "Event / album",
    "keywords": "Tags / keywords",
    "rating": "Star rating",
    "date_taken": "Date taken",
}

DEFAULT_SIDECAR_MAPPING: dict[str, list[str]] = {
    "caption": [
        "caption", "description", "comment", "title",
        "ImageDescription", "userComment", "UserComment",
        "dc:description", "dc:title", "photoshop:Headline",
    ],
    "event": [
        "event", "eventName", "event_name", "album", "albumName", "album_name",
        "Iptc4xmpCore:Event",
    ],
    "keywords": [
        "keywords", "tags", "keyword", "labels", "subjects",
        "dc:subject", "subject",
    ],
    "rating": [
        "rating", "stars", "starRating", "star_rating", "Rating",
        "xmp:Rating",
    ],
    "date_taken": [
        "dateTaken", "date_taken", "DateTimeOriginal", "created", "createdAt",
        "created_at", "takenAt", "taken_at", "date", "captureDate", "capture_date",
        "exif:DateTimeOriginal", "photoshop:DateCreated", "xmp:CreateDate",
    ],
}

SCAN_DEPTH_OPTIONS = ("All files", "Last 7 days", "Last 30 days", "Last 90 days")

SCAN_DEPTH_DAYS = {
    "All files": None,
    "Last 7 days": 7,
    "Last 30 days": 30,
    "Last 90 days": 90,
}

_cached_app_settings: Optional["AppSettings"] = None


@dataclass
class AppSettings:
    appearance_mode: str = APPEARANCE_MODES[0]
    auto_save_metadata: bool = True
    auto_save_delay_ms: int = 800
    sidecar_field_mapping: dict[str, list[str]] = field(
        default_factory=lambda: deepcopy(DEFAULT_SIDECAR_MAPPING),
    )
    metadata_panel_collapsed: bool = False
    gallery_sort: str = GALLERY_SORT_OPTIONS[0]
    scan_depth_label: str = "Last 30 days"
    idle_duplicate_scan_enabled: bool = False
    idle_duplicate_scan_folder: str = ""
    idle_duplicate_scan_days: int = 30
    idle_duplicate_scan_idle_minutes: int = 5
    idle_duplicate_scan_cooldown_hours: int = 6
    last_idle_duplicate_scan_at: float = 0.0
    suppress_config_warnings: bool = False
    suppress_ffmpeg_warning: bool = False
    phash_tolerance: int = 5
    video_duplicate_tolerance: int = 3
    conflict_policy: str = "rename"
    folder_template: str = ""
    filename_template: str = ""
    ollama_url: str = "http://localhost:11434"
    enable_local_ai: bool = False
    snapshot_before_delete: bool = True
    use_media_index: bool = True
    recent_scan_folders: list[str] = field(default_factory=list)
    auto_ocr_on_folder_load: bool = False
    custom_accent: str = ""
    theme_preset: str = DEFAULT_PRESET_ID
    keyboard_shortcuts: dict[str, str] = field(default_factory=dict)
    locale: str = "en"
    idle_duplicate_scan_cpu_limit: int = 50
    idle_duplicate_scan_skip_on_battery: bool = True
    idle_duplicate_scan_only_when_locked: bool = False


def set_app_settings_cache(settings: AppSettings) -> None:
    global _cached_app_settings
    _cached_app_settings = settings


def clear_app_settings_cache() -> None:
    global _cached_app_settings
    _cached_app_settings = None


def _normalize_mapping(raw: Any) -> dict[str, list[str]]:
    if not isinstance(raw, dict):
        return deepcopy(DEFAULT_SIDECAR_MAPPING)
    result = deepcopy(DEFAULT_SIDECAR_MAPPING)
    for key in SIDECAR_FIELD_LABELS:
        value = raw.get(key)
        if isinstance(value, list):
            cleaned = [str(v).strip() for v in value if str(v).strip()]
            if cleaned:
                result[key] = cleaned
        elif isinstance(value, str) and value.strip():
            result[key] = [k.strip() for k in value.split(",") if k.strip()]
    return result


def _normalize_gallery_sort(value: Any) -> str:
    if value in GALLERY_SORT_OPTIONS:
        return value
    return GALLERY_SORT_OPTIONS[0]


def _normalize_appearance_mode(value: Any) -> str:
    if value in APPEARANCE_MODES:
        return value
    return APPEARANCE_MODES[0]


def _normalize_scan_depth(value: Any) -> str:
    if value in SCAN_DEPTH_OPTIONS:
        return value
    return "Last 30 days"


def _normalize_conflict_policy(value: Any) -> str:
    v = str(value or "rename").lower()
    return v if v in CONFLICT_POLICIES else "rename"


def _normalize_phash_tolerance(value: Any) -> int:
    try:
        return max(0, min(16, int(value)))
    except (TypeError, ValueError):
        return 5


def _normalize_video_duplicate_tolerance(value: Any) -> int:
    try:
        return max(0, min(16, int(value)))
    except (TypeError, ValueError):
        return 3


def _normalize_recent_folders(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        p = str(item or "").strip()
        if p and p not in out:
            out.append(p)
    return out[:5]


def _normalize_accent(value: Any) -> str:
    text = str(value or "").strip()
    if text.startswith("#") and len(text) in (4, 7):
        return text
    return ""


def _normalize_shortcuts(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(k): str(v) for k, v in value.items() if str(k).strip() and str(v).strip()}


def push_recent_scan_folder(path: str) -> None:
    path = str(path or "").strip()
    if not path:
        return
    settings = load_app_settings()
    folders = [path] + [p for p in settings.recent_scan_folders if p != path]
    settings.recent_scan_folders = folders[:5]
    save_app_settings(settings)


def parse_app_settings(data: dict) -> AppSettings:
    """Parse and normalize app settings from a JSON dict."""
    return AppSettings(
        appearance_mode=_normalize_appearance_mode(data.get("appearance_mode")),
        auto_save_metadata=bool(data.get("auto_save_metadata", True)),
        auto_save_delay_ms=max(300, int(data.get("auto_save_delay_ms", 800))),
        sidecar_field_mapping=_normalize_mapping(data.get("sidecar_field_mapping")),
        metadata_panel_collapsed=bool(data.get("metadata_panel_collapsed", False)),
        gallery_sort=_normalize_gallery_sort(data.get("gallery_sort")),
        scan_depth_label=_normalize_scan_depth(data.get("scan_depth_label")),
        idle_duplicate_scan_enabled=bool(data.get("idle_duplicate_scan_enabled", False)),
        idle_duplicate_scan_folder=str(data.get("idle_duplicate_scan_folder", "") or ""),
        idle_duplicate_scan_days=max(1, int(data.get("idle_duplicate_scan_days", 30))),
        idle_duplicate_scan_idle_minutes=max(1, int(data.get("idle_duplicate_scan_idle_minutes", 5))),
        idle_duplicate_scan_cooldown_hours=max(1, int(data.get("idle_duplicate_scan_cooldown_hours", 6))),
        last_idle_duplicate_scan_at=float(data.get("last_idle_duplicate_scan_at", 0) or 0),
        suppress_config_warnings=bool(data.get("suppress_config_warnings", False)),
        suppress_ffmpeg_warning=bool(data.get("suppress_ffmpeg_warning", False)),
        phash_tolerance=_normalize_phash_tolerance(data.get("phash_tolerance", 5)),
        video_duplicate_tolerance=_normalize_video_duplicate_tolerance(
            data.get("video_duplicate_tolerance", 3),
        ),
        conflict_policy=_normalize_conflict_policy(data.get("conflict_policy")),
        folder_template=str(data.get("folder_template", "") or ""),
        filename_template=str(data.get("filename_template", "") or ""),
        ollama_url=str(data.get("ollama_url", "http://localhost:11434") or "http://localhost:11434"),
        enable_local_ai=bool(data.get("enable_local_ai", False)),
        snapshot_before_delete=bool(data.get("snapshot_before_delete", True)),
        use_media_index=bool(data.get("use_media_index", True)),
        recent_scan_folders=_normalize_recent_folders(data.get("recent_scan_folders")),
        auto_ocr_on_folder_load=bool(data.get("auto_ocr_on_folder_load", False)),
        custom_accent=_normalize_accent(data.get("custom_accent")),
        theme_preset=normalize_preset_id(data.get("theme_preset")),
        keyboard_shortcuts=_normalize_shortcuts(data.get("keyboard_shortcuts")),
        locale=str(data.get("locale", "en") or "en"),
        idle_duplicate_scan_cpu_limit=max(10, min(100, int(data.get("idle_duplicate_scan_cpu_limit", 50)))),
        idle_duplicate_scan_skip_on_battery=bool(data.get("idle_duplicate_scan_skip_on_battery", True)),
        idle_duplicate_scan_only_when_locked=bool(data.get("idle_duplicate_scan_only_when_locked", False)),
    )


def app_settings_to_payload(settings: AppSettings) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "appearance_mode": settings.appearance_mode,
        "auto_save_metadata": settings.auto_save_metadata,
        "auto_save_delay_ms": settings.auto_save_delay_ms,
        "sidecar_field_mapping": settings.sidecar_field_mapping,
        "metadata_panel_collapsed": settings.metadata_panel_collapsed,
        "gallery_sort": settings.gallery_sort,
        "scan_depth_label": settings.scan_depth_label,
        "idle_duplicate_scan_enabled": settings.idle_duplicate_scan_enabled,
        "idle_duplicate_scan_folder": settings.idle_duplicate_scan_folder,
        "idle_duplicate_scan_days": settings.idle_duplicate_scan_days,
        "idle_duplicate_scan_idle_minutes": settings.idle_duplicate_scan_idle_minutes,
        "idle_duplicate_scan_cooldown_hours": settings.idle_duplicate_scan_cooldown_hours,
        "last_idle_duplicate_scan_at": settings.last_idle_duplicate_scan_at,
        "suppress_config_warnings": settings.suppress_config_warnings,
        "suppress_ffmpeg_warning": settings.suppress_ffmpeg_warning,
        "phash_tolerance": settings.phash_tolerance,
        "video_duplicate_tolerance": settings.video_duplicate_tolerance,
        "conflict_policy": settings.conflict_policy,
        "folder_template": settings.folder_template,
        "filename_template": settings.filename_template,
        "ollama_url": settings.ollama_url,
        "enable_local_ai": settings.enable_local_ai,
        "snapshot_before_delete": settings.snapshot_before_delete,
        "use_media_index": settings.use_media_index,
        "recent_scan_folders": list(settings.recent_scan_folders),
        "auto_ocr_on_folder_load": settings.auto_ocr_on_folder_load,
        "custom_accent": settings.custom_accent,
        "theme_preset": settings.theme_preset,
        "keyboard_shortcuts": dict(settings.keyboard_shortcuts),
        "locale": settings.locale,
        "idle_duplicate_scan_cpu_limit": settings.idle_duplicate_scan_cpu_limit,
        "idle_duplicate_scan_skip_on_battery": settings.idle_duplicate_scan_skip_on_battery,
        "idle_duplicate_scan_only_when_locked": settings.idle_duplicate_scan_only_when_locked,
    }


def scan_depth_to_days(label: str) -> Optional[int]:
    return SCAN_DEPTH_DAYS.get(label)


def settings_path() -> Path:
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    return APP_SETTINGS_FILE


def atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def load_app_settings() -> AppSettings:
    if _cached_app_settings is not None:
        return _cached_app_settings

    path = settings_path()
    if not path.is_file():
        default = AppSettings()
        save_app_settings(default)
        return default

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("app_settings.json root must be an object")
        settings = parse_app_settings(data)
        set_app_settings_cache(settings)
        return settings
    except (json.JSONDecodeError, OSError, TypeError, ValueError) as e:
        logger.warning("Could not load app settings: %s", e)
        return AppSettings()


def save_app_settings(settings: AppSettings):
    path = settings_path()
    atomic_write_json(path, app_settings_to_payload(settings))
    set_app_settings_cache(settings)


def load_sidecar_mapping() -> dict[str, list[str]]:
    return load_app_settings().sidecar_field_mapping


def mapping_to_display(mapping: dict[str, list[str]]) -> dict[str, str]:
    """Comma-separated strings for UI entry fields."""
    return {key: ", ".join(mapping.get(key, [])) for key in SIDECAR_FIELD_LABELS}


def mapping_from_display(display: dict[str, str]) -> dict[str, list[str]]:
    result = deepcopy(DEFAULT_SIDECAR_MAPPING)
    for key, text in display.items():
        if key not in SIDECAR_FIELD_LABELS:
            continue
        keys = [k.strip() for k in text.split(",") if k.strip()]
        if keys:
            result[key] = keys
    return result


__all__ = [
    "APP_SETTINGS_FILE",
    "AppSettings",
    "CONFLICT_POLICIES",
    "DEFAULT_SIDECAR_MAPPING",
    "GALLERY_SORT_OPTIONS",
    "KNOWN_APP_KEYS",
    "SCAN_DEPTH_DAYS",
    "SCAN_DEPTH_OPTIONS",
    "SCHEMA_VERSION",
    "SETTINGS_DIR",
    "SIDECAR_FIELD_LABELS",
    "app_settings_to_payload",
    "atomic_write_json",
    "clear_app_settings_cache",
    "load_app_settings",
    "load_sidecar_mapping",
    "mapping_from_display",
    "mapping_to_display",
    "parse_app_settings",
    "push_recent_scan_folder",
    "save_app_settings",
    "scan_depth_to_days",
    "set_app_settings_cache",
    "settings_path",
]
