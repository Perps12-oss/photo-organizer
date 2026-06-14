"""
Background inbox watcher — monitors a folder and routes files via OrganizerEngine.
"""
import json
import logging
import os
import sys
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from organizer_engine import (
    DateSource,
    FileScope,
    LayoutMode,
    NameMode,
    OrganizerConfig,
    OrganizerEngine,
)

try:
    import pystray
    from PIL import Image, ImageDraw

    HAS_PYSTRAY = True
except ImportError:
    HAS_PYSTRAY = False

logger = logging.getLogger(__name__)

SKIP_SUFFIXES = (".tmp", ".part", ".crdownload", ".download", ".partial", ".lock")
SKIP_PREFIXES = (".", "~")

SETTINGS_DIR = Path(os.environ.get("APPDATA", os.path.expanduser("~"))) / "PhotoOrganizer"
SETTINGS_FILE = SETTINGS_DIR / "watcher_settings.json"
STATS_FILE = SETTINGS_DIR / "watcher_stats.json"
AUTOSTART_BAT = "PhotoOrganizer_Watcher.bat"

SCHEMA_VERSION = 1

KNOWN_WATCHER_KEYS = frozenset({
    "schema_version",
    "library_root",
    "inbox_relative",
    "action",
    "poll_seconds",
    "layout",
    "date_source",
    "scope",
    "name_mode",
    "start_on_launch",
    "run_at_login",
    "minimize_to_tray",
    "recursive",
})

VALID_ACTIONS = frozenset({"move", "copy"})

_cached_watcher_settings: Optional["WatcherSettings"] = None


@dataclass
class WatcherSettings:
    library_root: str = ""
    inbox_relative: str = "01_Inbox"
    action: str = "move"
    poll_seconds: float = 2.0
    layout: str = LayoutMode.MEDIA_LIBRARY.value
    date_source: str = DateSource.MODIFIED.value
    scope: str = FileScope.ALL_MEDIA.value
    name_mode: str = NameMode.PREFIX_DATE.value
    start_on_launch: bool = False
    run_at_login: bool = False
    minimize_to_tray: bool = True
    recursive: bool = True


def set_watcher_settings_cache(settings: "WatcherSettings") -> None:
    global _cached_watcher_settings
    _cached_watcher_settings = settings


def clear_watcher_settings_cache() -> None:
    global _cached_watcher_settings
    _cached_watcher_settings = None


def _enum_value(enum_cls, value, default):
    if value is not None:
        for member in enum_cls:
            if member.value == value:
                return member.value
    return default.value


def parse_watcher_settings(data: dict) -> WatcherSettings:
    """Parse and normalize watcher settings from a JSON dict."""
    library_root = os.path.expanduser(str(data.get("library_root", "") or ""))
    inbox_relative = str(data.get("inbox_relative", "01_Inbox") or "01_Inbox").strip()
    if not inbox_relative:
        inbox_relative = "01_Inbox"
    if os.path.isabs(inbox_relative):
        inbox_relative = "01_Inbox"

    action = str(data.get("action", "move") or "move").lower()
    if action not in VALID_ACTIONS:
        action = "move"

    try:
        poll_seconds = max(0.5, float(data.get("poll_seconds", 2.0)))
    except (TypeError, ValueError):
        poll_seconds = 2.0

    return WatcherSettings(
        library_root=library_root,
        inbox_relative=inbox_relative,
        action=action,
        poll_seconds=poll_seconds,
        layout=_enum_value(LayoutMode, data.get("layout"), LayoutMode.MEDIA_LIBRARY),
        date_source=_enum_value(DateSource, data.get("date_source"), DateSource.MODIFIED),
        scope=_enum_value(FileScope, data.get("scope"), FileScope.ALL_MEDIA),
        name_mode=_enum_value(NameMode, data.get("name_mode"), NameMode.PREFIX_DATE),
        start_on_launch=bool(data.get("start_on_launch", False)),
        run_at_login=bool(data.get("run_at_login", False)),
        minimize_to_tray=bool(data.get("minimize_to_tray", True)),
        recursive=bool(data.get("recursive", True)),
    )


def watcher_settings_to_payload(settings: WatcherSettings) -> dict:
    payload = asdict(settings)
    payload["schema_version"] = SCHEMA_VERSION
    return payload


def settings_path() -> Path:
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    return SETTINGS_FILE


def load_settings() -> WatcherSettings:
    if _cached_watcher_settings is not None:
        return _cached_watcher_settings
    path = settings_path()
    if not path.exists():
        default = WatcherSettings(library_root=os.path.expanduser("~/Media_Library"))
        save_settings(default)
        return default
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("watcher_settings.json root must be an object")
        settings = parse_watcher_settings(data)
        set_watcher_settings_cache(settings)
        return settings
    except (json.JSONDecodeError, OSError, TypeError, ValueError) as e:
        logger.warning("Could not load watcher settings: %s", e)
        return WatcherSettings(library_root=os.path.expanduser("~/Media_Library"))


def save_settings(settings: WatcherSettings):
    from app_settings import atomic_write_json

    path = settings_path()
    atomic_write_json(path, watcher_settings_to_payload(settings))
    set_watcher_settings_cache(settings)


def settings_to_config(settings: WatcherSettings) -> OrganizerConfig:
    def _enum(enum_cls, value):
        for member in enum_cls:
            if member.value == value:
                return member
        return list(enum_cls)[0]

    return OrganizerConfig(
        layout=_enum(LayoutMode, settings.layout),
        date_source=_enum(DateSource, settings.date_source),
        scope=_enum(FileScope, settings.scope),
        name_mode=_enum(NameMode, settings.name_mode),
    )


def inbox_path(settings: WatcherSettings) -> str:
    return os.path.join(settings.library_root, settings.inbox_relative)


def _startup_folder() -> Path:
    return Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def autostart_script_path() -> Path:
    return _startup_folder() / AUTOSTART_BAT


def set_windows_autostart(enable: bool, entry_script: Optional[Path] = None) -> tuple[bool, str]:
    if sys.platform != "win32":
        return False, "Windows login startup is only supported on Windows."
    if entry_script is None:
        entry_script = Path(__file__).resolve().parent / "photo_organizer_enhanced.py"
    app_dir = entry_script.parent
    bat_path = autostart_script_path()
    try:
        if enable:
            _startup_folder().mkdir(parents=True, exist_ok=True)
            launcher = (
                f'@echo off\r\ncd /d "{app_dir}"\r\n'
                f'start "" pythonw "{entry_script.name}" --minimized --auto-watch\r\n'
            )
            bat_path.write_text(launcher, encoding="utf-8")
            return True, f"Created startup entry:\n{bat_path}"
        if bat_path.exists():
            bat_path.unlink()
        return True, "Removed Windows login startup entry."
    except OSError as e:
        return False, str(e)


def is_windows_autostart_enabled() -> bool:
    return autostart_script_path().exists()


def load_watcher_stats() -> dict:
    if not STATS_FILE.is_file():
        return {}
    try:
        return json.loads(STATS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_watcher_stats(stats: dict):
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    STATS_FILE.write_text(json.dumps(stats, indent=2), encoding="utf-8")


def should_skip_file(name: str) -> bool:
    lower = name.lower()
    if any(lower.endswith(s) for s in SKIP_SUFFIXES):
        return True
    if any(name.startswith(p) for p in SKIP_PREFIXES):
        return True
    return False


def wait_for_stable_file(filepath: str, checks: int = 2, interval: float = 1.0, timeout: float = 60.0) -> bool:
    """Wait until file size is unchanged for `checks` consecutive polls."""
    deadline = time.monotonic() + timeout
    last_size = -1
    stable = 0
    while time.monotonic() < deadline:
        try:
            size = os.path.getsize(filepath)
        except OSError:
            return False
        if size == last_size and size > 0:
            stable += 1
            if stable >= checks:
                return True
        else:
            stable = 0
            last_size = size
        time.sleep(interval)
    return False


class InboxWatcher:
    """Poll-based inbox monitor that routes files through OrganizerEngine."""

    def __init__(
        self,
        on_log: Optional[Callable[[str], None]] = None,
        on_processed: Optional[Callable[[str, str], None]] = None,
    ):
        self.on_log = on_log or (lambda msg: logger.info(msg))
        self.on_processed = on_processed
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self.running = False
        self.files_processed = 0
        self.last_processed_file = ""
        self.last_processed_dest = ""
        self.settings = load_settings()
        self.engine = OrganizerEngine(settings_to_config(self.settings))
        self._load_daily_stats()

    def _load_daily_stats(self):
        stats = load_watcher_stats()
        today_str = datetime.now().strftime("%Y-%m-%d")
        if stats.get("date") == today_str:
            self.files_processed_today = int(stats.get("count", 0))
            self.last_processed_file = stats.get("last_file", "")
            self.last_processed_dest = stats.get("last_dest", "")
        else:
            self.files_processed_today = 0

    def _record_processed(self, filepath: str, dest: str):
        self.last_processed_file = os.path.basename(filepath)
        self.last_processed_dest = dest
        self.files_processed_today += 1
        save_watcher_stats({
            "date": datetime.now().strftime("%Y-%m-%d"),
            "count": self.files_processed_today,
            "last_file": self.last_processed_file,
            "last_dest": self.last_processed_dest,
        })

    def log(self, msg: str):
        stamp = datetime.now().strftime("%H:%M:%S")
        self.on_log(f"[{stamp}] {msg}")

    def update_settings(self, settings: WatcherSettings):
        with self._lock:
            self.settings = settings
            self.engine.set_config(settings_to_config(settings))
            save_settings(settings)

    def start(self, settings: Optional[WatcherSettings] = None) -> tuple[bool, str]:
        if settings:
            self.update_settings(settings)
        with self._lock:
            if self.running:
                return False, "Watcher is already running."
            root = self.settings.library_root.strip()
            if not root:
                return False, "Set a media library root path first."
            os.makedirs(inbox_path(self.settings), exist_ok=True)
            if self.settings.layout == LayoutMode.MEDIA_LIBRARY.value:
                OrganizerEngine.ensure_media_library_tree(root)
            self._stop.clear()
            self.running = True
            self._thread = threading.Thread(target=self._watch_loop, daemon=True)
            self._thread.start()
        self.log(f"Watching {inbox_path(self.settings)}")
        return True, "Watcher started."

    def stop(self) -> tuple[bool, str]:
        with self._lock:
            if not self.running:
                return False, "Watcher is not running."
            self._stop.set()
            thread = self._thread
        if thread:
            thread.join(timeout=10)
        with self._lock:
            self.running = False
            self._thread = None
        self.log("Watcher stopped.")
        return True, "Watcher stopped."

    def _iter_inbox_files(self) -> list[str]:
        watch_dir = inbox_path(self.settings)
        found = []
        if self.settings.recursive:
            for root, _, files in os.walk(watch_dir):
                for name in files:
                    if not should_skip_file(name):
                        found.append(os.path.join(root, name))
        else:
            for name in os.listdir(watch_dir):
                full = os.path.join(watch_dir, name)
                if os.path.isfile(full) and not should_skip_file(name):
                    found.append(full)
        return found

    def _watch_loop(self):
        seen: set[str] = set()
        while not self._stop.is_set():
            try:
                for filepath in self._iter_inbox_files():
                    if self._stop.is_set():
                        break
                    if filepath in seen:
                        continue
                    if not wait_for_stable_file(filepath, timeout=30):
                        continue
                    seen.add(filepath)
                    with self._lock:
                        action = self.settings.action
                        dest_root = self.settings.library_root
                        self.engine.set_config(settings_to_config(self.settings))
                    ok, result = self.engine.organize_file(filepath, dest_root, action)
                    if ok:
                        self.files_processed += 1
                        self._record_processed(filepath, result)
                        self.log(f"Moved -> {result}" if action == "move" else f"Copied -> {result}")
                        if self.on_processed:
                            self.on_processed(filepath, result)
                    elif result != "skipped (no match)":
                        self.log(f"Error: {os.path.basename(filepath)} — {result}")
                    else:
                        seen.discard(filepath)
            except Exception as e:
                self.log(f"Watcher error: {e}")
            self._stop.wait(self.settings.poll_seconds)
        with self._lock:
            self.running = False


def _make_tray_image(size: int = 64) -> "Image.Image":
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((4, 4, size - 4, size - 4), fill=(0, 255, 204, 255))
    draw.rectangle((18, 22, 46, 48), fill=(10, 10, 18, 255))
    draw.polygon([(16, 22), (32, 12), (48, 22)], fill=(26, 26, 46, 255))
    return img


class TrayController:
    """Optional system tray icon (requires pystray)."""

    def __init__(
        self,
        on_show: Callable[[], None],
        on_toggle_watch: Callable[[], None],
        on_quit: Callable[[], None],
        is_watching: Callable[[], bool],
        get_stats: Optional[Callable[[], tuple[int, int]]] = None,
    ):
        self.on_show = on_show
        self.on_toggle_watch = on_toggle_watch
        self.on_quit = on_quit
        self.is_watching = is_watching
        self.get_stats = get_stats or (lambda: (0, 0))
        self._icon: Optional[pystray.Icon] = None
        self._thread: Optional[threading.Thread] = None

    @staticmethod
    def available() -> bool:
        return HAS_PYSTRAY

    def start(self):
        if not HAS_PYSTRAY or self._icon:
            return
        menu = pystray.Menu(
            pystray.MenuItem("Open Photo Organizer", lambda *_: self.on_show()),
            pystray.MenuItem(lambda item: self._stats_label(), None, enabled=False),
            pystray.MenuItem(lambda item: self._watch_label(), lambda *_: self.on_toggle_watch()),
            pystray.MenuItem("Exit", lambda *_: self._exit()),
        )
        self._icon = pystray.Icon("photo_organizer", _make_tray_image(), "Photo Organizer", menu)
        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()

    def _watch_label(self):
        return "Stop Inbox Watcher" if self.is_watching() else "Start Inbox Watcher"

    def _stats_label(self):
        session, today = self.get_stats()
        state = "Watching" if self.is_watching() else "Stopped"
        return f"{state} · Session {session} · Today {today}"

    def _exit(self):
        if self._icon:
            self._icon.stop()
        self.on_quit()

    def stop(self):
        if self._icon:
            self._icon.stop()
            self._icon = None

    def notify(self, title: str, message: str):
        if self._icon:
            try:
                self._icon.notify(message, title)
            except Exception:
                pass
