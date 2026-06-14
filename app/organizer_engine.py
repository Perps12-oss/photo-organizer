"""
Rules-based file organizer engine — sort, copy, move by configurable layout.
"""
import datetime
import mimetypes
import os
import shutil
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp", ".heic", ".heif"}
VIDEO_EXT = {".mov", ".mp4", ".avi", ".mkv", ".webm", ".m4v"}
AUDIO_EXT = {".mp3", ".flac", ".wav", ".aac", ".m4a", ".ogg", ".wma"}
DOC_EXT = {".pdf", ".doc", ".docx", ".txt", ".xlsx", ".xls", ".pptx", ".ppt", ".csv", ".rtf"}
PHOTOS_VIDEOS_EXT = IMAGE_EXT | VIDEO_EXT
ALL_MEDIA_EXT = PHOTOS_VIDEOS_EXT | AUDIO_EXT | DOC_EXT

MEDIA_LIBRARY_DIRS = (
    "01_Inbox/_Unsorted",
    "02_Documents/_Incoming",
    "03_Images",
    "04_Music/_ToBeTagged",
    "05_Archive",
)


class LayoutMode(Enum):
    FLAT = "Put all files directly in destination (no subfolders)"
    YEAR = "Year folders (YYYY/)"
    YEAR_MONTH = "Year-month folders (YYYY-MM/)"
    YEAR_MONTH_DAY = "Day folders (YYYY-MM-DD/)"
    MEDIA_LIBRARY = "Media library (Images / Documents / Music / Inbox)"


class DateSource(Enum):
    MODIFIED = "File modified date"
    CREATED = "File created date"
    EXIF = "Photo EXIF date (fallback: modified)"


class FileScope(Enum):
    PHOTOS_VIDEOS = "Photos & videos"
    IMAGES_ONLY = "Images only"
    ALL_MEDIA = "Photos, video, audio & documents"
    ALL_FILES = "All files (any extension)"


class NameMode(Enum):
    KEEP = "Keep original filename"
    PREFIX_DATE = "Prefix filename with date (YYYYMMDD_)"


class ConflictPolicy(Enum):
    RENAME = "rename"
    SKIP = "skip"
    OVERWRITE = "overwrite"


def resolve_template(
    template: str,
    filepath: str,
    dt: datetime.datetime,
    *,
    event: str = "",
    artist: str = "",
    category: str = "",
) -> str:
    """Expand {date}, {year}, {month}, {extension}, {name}, {stem}, {event}, {artist}, {category}."""
    if not template:
        return ""
    name = os.path.basename(filepath)
    stem, ext = os.path.splitext(name)
    mapping = {
        "date": dt.strftime("%Y-%m-%d"),
        "date_compact": dt.strftime("%Y%m%d"),
        "year": dt.strftime("%Y"),
        "month": dt.strftime("%m"),
        "day": dt.strftime("%d"),
        "extension": ext.lstrip(".").lower(),
        "ext": ext,
        "name": name,
        "stem": stem,
        "event": event or "",
        "artist": artist or "",
        "category": category or "",
    }
    result = template
    for key, val in mapping.items():
        result = result.replace("{" + key + "}", val)
    return result.replace("\\", "/").strip("/")


@dataclass
class OrganizerConfig:
    layout: LayoutMode = LayoutMode.YEAR_MONTH
    date_source: DateSource = DateSource.MODIFIED
    scope: FileScope = FileScope.PHOTOS_VIDEOS
    name_mode: NameMode = NameMode.KEEP
    conflict_policy: ConflictPolicy = ConflictPolicy.RENAME
    folder_template: str = ""
    filename_template: str = ""


@dataclass
class OrganizePlanItem:
    source: str
    destination: str
    folder_key: str


class OrganizerEngine:
    """Scan, plan, preview, and execute file organization."""

    def __init__(self, config: Optional[OrganizerConfig] = None):
        self.config = config or OrganizerConfig()

    def set_config(self, config: OrganizerConfig):
        self.config = config

    def extensions_for_scope(self) -> Optional[set]:
        scope = self.config.scope
        if scope == FileScope.PHOTOS_VIDEOS:
            return PHOTOS_VIDEOS_EXT
        if scope == FileScope.IMAGES_ONLY:
            return IMAGE_EXT
        if scope == FileScope.ALL_MEDIA:
            return ALL_MEDIA_EXT
        return None  # all files

    def file_matches(self, filename: str) -> bool:
        ext = os.path.splitext(filename)[1].lower()
        allowed = self.extensions_for_scope()
        if allowed is None:
            return True
        return ext in allowed

    def get_file_date(self, filepath: str) -> datetime.datetime:
        cfg = self.config.date_source
        if cfg == DateSource.EXIF:
            exif_dt = self._exif_datetime(filepath)
            if exif_dt:
                return exif_dt
        if cfg == DateSource.CREATED:
            try:
                return datetime.datetime.fromtimestamp(os.path.getctime(filepath))
            except OSError:
                pass
        return datetime.datetime.fromtimestamp(os.path.getmtime(filepath))

    def _exif_datetime(self, filepath: str) -> Optional[datetime.datetime]:
        if not HAS_PIL or os.path.splitext(filepath)[1].lower() not in IMAGE_EXT:
            return None
        try:
            with Image.open(filepath) as img:
                exif = img.getexif()
                if not exif:
                    return None
                # 36867 = DateTimeOriginal, 306 = DateTime
                for tag in (36867, 306):
                    raw = exif.get(tag)
                    if raw:
                        return datetime.datetime.strptime(str(raw), "%Y:%m:%d %H:%M:%S")
        except Exception:
            pass
        return None

    def _category_for_file(self, filepath: str) -> str:
        ext = os.path.splitext(filepath)[1].lower()
        mime, _ = mimetypes.guess_type(filepath)
        if ext in IMAGE_EXT or (mime and mime.startswith("image/")):
            return "image"
        if ext in VIDEO_EXT or (mime and mime.startswith("video/")):
            return "video"
        if ext in AUDIO_EXT or (mime and mime.startswith("audio/")):
            return "audio"
        if ext in DOC_EXT or (mime and mime.startswith("application/")):
            return "document"
        return "other"

    def folder_key_for_date(self, dt: datetime.datetime) -> str:
        layout = self.config.layout
        if layout == LayoutMode.FLAT:
            return "(root)"
        if layout == LayoutMode.YEAR:
            return dt.strftime("%Y")
        if layout == LayoutMode.YEAR_MONTH:
            return dt.strftime("%Y-%m")
        if layout == LayoutMode.YEAR_MONTH_DAY:
            return dt.strftime("%Y-%m-%d")
        return dt.strftime("%Y-%m")

    def dest_subfolder(self, filepath: str, dt: datetime.datetime) -> str:
        layout = self.config.layout
        if layout == LayoutMode.MEDIA_LIBRARY:
            cat = self._category_for_file(filepath)
            date_part = dt.strftime("%Y/%Y-%m")
            if cat in ("image", "video"):
                return os.path.join("03_Images", date_part)
            if cat == "audio":
                return os.path.join("04_Music", "_ToBeTagged")
            if cat == "document":
                return os.path.join("02_Documents", "_Incoming")
            return os.path.join("01_Inbox", "_Unsorted")
        return self.folder_key_for_date(dt)

    def _optional_meta(self, filepath: str):
        template = (self.config.folder_template or "") + (self.config.filename_template or "")
        if "{event}" not in template and "{artist}" not in template:
            return None, ""
        try:
            from metadata_tools import read_metadata
            meta = read_metadata(filepath)
            return meta, meta.event or ""
        except Exception:
            return None, ""

    def dest_subfolder_resolved(self, filepath: str, dt: datetime.datetime) -> str:
        if self.config.folder_template.strip():
            meta, event = self._optional_meta(filepath)
            cat = self._category_for_file(filepath)
            sub = resolve_template(
                self.config.folder_template.strip(),
                filepath, dt, event=event, category=cat,
            )
            return sub if sub else self.dest_subfolder(filepath, dt)
        return self.dest_subfolder(filepath, dt)

    def dest_filename(self, filepath: str, dt: datetime.datetime) -> str:
        if self.config.filename_template.strip():
            meta, event = self._optional_meta(filepath)
            cat = self._category_for_file(filepath)
            out = resolve_template(
                self.config.filename_template.strip(),
                filepath, dt, event=event, category=cat,
            )
            if out:
                ext = os.path.splitext(filepath)[1]
                if not os.path.splitext(out)[1] and ext:
                    out += ext
                return out
        name = os.path.basename(filepath)
        if self.config.name_mode == NameMode.PREFIX_DATE:
            prefix = dt.strftime("%Y%m%d")
            if not name.startswith(prefix + "_"):
                return f"{prefix}_{name}"
        return name

    def unique_path(self, folder: str, filename: str) -> Optional[str]:
        dest = os.path.join(folder, filename)
        if not os.path.exists(dest):
            return dest
        policy = self.config.conflict_policy
        if policy == ConflictPolicy.SKIP:
            return None
        if policy == ConflictPolicy.OVERWRITE:
            return dest
        base, ext = os.path.splitext(filename)
        n = 1
        while True:
            candidate = os.path.join(folder, f"{base}_{n}{ext}")
            if not os.path.exists(candidate):
                return candidate
            n += 1

    def build_plan(self, source: str, dest_root: str) -> list[OrganizePlanItem]:
        plan = []
        for root, _, files in os.walk(source):
            for fname in files:
                if not self.file_matches(fname):
                    continue
                src = os.path.join(root, fname)
                try:
                    dt = self.get_file_date(src)
                    sub = self.dest_subfolder_resolved(src, dt)
                    folder = os.path.join(dest_root, sub) if sub != "(root)" else dest_root
                    out_name = self.dest_filename(src, dt)
                    dst = self.unique_path(folder, out_name)
                    if dst is None:
                        continue
                    key = sub.replace("\\", "/")
                    plan.append(OrganizePlanItem(src, dst, key))
                except OSError:
                    continue
        return plan

    def plan_file(self, filepath: str, dest_root: str) -> Optional[OrganizePlanItem]:
        """Build a plan item for one file, or None if it does not match scope."""
        if not os.path.isfile(filepath):
            return None
        fname = os.path.basename(filepath)
        if not self.file_matches(fname):
            return None
        try:
            dt = self.get_file_date(filepath)
            sub = self.dest_subfolder_resolved(filepath, dt)
            folder = os.path.join(dest_root, sub) if sub != "(root)" else dest_root
            out_name = self.dest_filename(filepath, dt)
            dst = self.unique_path(folder, out_name)
            if dst is None:
                return None
            key = sub.replace("\\", "/")
            return OrganizePlanItem(filepath, dst, key)
        except OSError:
            return None

    def organize_file(self, filepath: str, dest_root: str, action: str = "move") -> tuple[bool, str]:
        """Organize a single file. Returns (success, destination path or error message)."""
        item = self.plan_file(filepath, dest_root)
        if not item:
            return False, "skipped (no match)"
        if self.config.layout == LayoutMode.MEDIA_LIBRARY:
            self.ensure_media_library_tree(dest_root)
        try:
            os.makedirs(os.path.dirname(item.destination), exist_ok=True)
            if action == "move":
                shutil.move(item.source, item.destination)
            else:
                shutil.copy2(item.source, item.destination)
            return True, item.destination
        except Exception as e:
            return False, str(e)

    def summarize_plan(self, plan: list[OrganizePlanItem]) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for item in plan:
            counts[item.folder_key] += 1
        return dict(counts)

    def format_preview(self, plan: list[OrganizePlanItem], dest_root: str, action: str) -> str:
        if not plan:
            return "No matching files found in the source folder."
        summary = self.summarize_plan(plan)
        lines = [
            f"Files to {action}: {len(plan)}",
            f"Destination root: {dest_root}",
            f"Layout: {self.config.layout.name.replace('_', ' ').title()}",
            f"Date from: {self.config.date_source.value}",
            "",
            "Folders that will be created or used:",
        ]
        for key in sorted(summary.keys()):
            lines.append(f"  {key}/  —  {summary[key]} file(s)")
        if len(summary) > 25:
            lines.append(f"  ... ({len(summary)} folders total)")
        return "\n".join(lines)

    @staticmethod
    def ensure_media_library_tree(dest_root: str):
        for sub in MEDIA_LIBRARY_DIRS:
            os.makedirs(os.path.join(dest_root, sub), exist_ok=True)

    def execute(
        self,
        plan: list[OrganizePlanItem],
        action: str,
        dest_root: str = "",
        on_progress: Optional[Callable[[float, int, int], None]] = None,
        on_item_done: Optional[Callable[[OrganizePlanItem, str], None]] = None,
    ) -> tuple[int, list[str]]:
        total = len(plan)
        done = 0
        errors = []
        if self.config.layout == LayoutMode.MEDIA_LIBRARY and dest_root:
            self.ensure_media_library_tree(dest_root)

        for item in plan:
            try:
                os.makedirs(os.path.dirname(item.destination), exist_ok=True)
                if (
                    self.config.conflict_policy == ConflictPolicy.OVERWRITE
                    and os.path.exists(item.destination)
                ):
                    if action == "move" and os.path.samefile(item.source, item.destination):
                        done += 1
                        continue
                    if os.path.isfile(item.destination):
                        os.remove(item.destination)
                if action == "move":
                    shutil.move(item.source, item.destination)
                else:
                    shutil.copy2(item.source, item.destination)
                done += 1
                if on_item_done:
                    on_item_done(item, action)
            except Exception as e:
                errors.append(f"{os.path.basename(item.source)}: {e}")
            if on_progress:
                on_progress(done / max(total, 1), done, total)
        return done, errors
