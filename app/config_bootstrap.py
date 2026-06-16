"""
Startup config validation — load, migrate, backup, and cache app + watcher settings.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

from app_settings import (
    APP_SETTINGS_FILE,
    KNOWN_APP_KEYS,
    SCHEMA_VERSION as APP_SCHEMA_VERSION,
    AppSettings,
    SETTINGS_DIR,
    app_settings_to_payload,
    parse_app_settings,
    save_app_settings,
    set_app_settings_cache,
)
from inbox_watcher import (
    KNOWN_WATCHER_KEYS,
    SCHEMA_VERSION as WATCHER_SCHEMA_VERSION,
    SETTINGS_FILE as WATCHER_SETTINGS_FILE,
    WatcherSettings,
    parse_watcher_settings,
    save_settings,
    set_watcher_settings_cache,
    watcher_settings_to_payload,
)

logger = logging.getLogger(__name__)

Severity = Literal["info", "warning", "error"]


@dataclass
class ConfigIssue:
    severity: Severity
    file: str
    field: str
    message: str
    action_taken: str = ""


@dataclass
class BootstrapResult:
    app_settings: AppSettings
    watcher_settings: WatcherSettings
    issues: list[ConfigIssue] = field(default_factory=list)
    migrated: bool = False
    backup_paths: list[Path] = field(default_factory=list)


def _backup_file(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = path.with_suffix(path.suffix + f".bak.{stamp}")
    if path.is_file():
        shutil.copy2(path, backup)
    return backup


def _unknown_keys(data: dict, known: frozenset) -> list[str]:
    return sorted(k for k in data if k not in known)


def _validate_app_paths(settings: AppSettings, issues: list[ConfigIssue]) -> None:
    if not settings.idle_duplicate_scan_enabled:
        return
    folder = (settings.idle_duplicate_scan_folder or "").strip()
    if not folder:
        return
    expanded = os.path.expanduser(folder)
    if not os.path.isdir(expanded):
        issues.append(ConfigIssue(
            severity="warning",
            file="app_settings.json",
            field="idle_duplicate_scan_folder",
            message=f"Idle scan folder does not exist or is not a directory: {expanded}",
            action_taken="idle scan may use library root until folder is fixed",
        ))


def _validate_watcher_paths(settings: WatcherSettings, issues: list[ConfigIssue]) -> None:
    root = (settings.library_root or "").strip()
    if not root:
        issues.append(ConfigIssue(
            severity="warning",
            file="watcher_settings.json",
            field="library_root",
            message="Library root is not set.",
            action_taken="set library root in File Organizer or Inbox Watcher",
        ))
        return
    expanded = os.path.expanduser(root)
    if not os.path.isdir(expanded):
        issues.append(ConfigIssue(
            severity="warning",
            file="watcher_settings.json",
            field="library_root",
            message=f"Library root does not exist or is not a directory: {expanded}",
            action_taken="app will start; organizer/watcher may fail until path is available",
        ))


def _bootstrap_app_settings() -> tuple[AppSettings, list[ConfigIssue], list[Path], bool]:
    issues: list[ConfigIssue] = []
    backups: list[Path] = []
    migrated = False
    path = APP_SETTINGS_FILE

    if not path.is_file():
        default = AppSettings()
        save_app_settings(default)
        issues.append(ConfigIssue(
            severity="info",
            file="app_settings.json",
            field="",
            message="Created default app settings.",
            action_taken="wrote defaults with schema_version",
        ))
        migrated = True
        return default, issues, backups, migrated

    raw_text = ""
    try:
        raw_text = path.read_text(encoding="utf-8")
        data = json.loads(raw_text)
        if not isinstance(data, dict):
            raise ValueError("root must be a JSON object")
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        backups.append(_backup_file(path))
        issues.append(ConfigIssue(
            severity="error",
            file="app_settings.json",
            field="",
            message=f"Could not read settings file: {exc}",
            action_taken="restored defaults; backup saved",
        ))
        default = AppSettings()
        save_app_settings(default)
        return default, issues, backups, True

    for key in _unknown_keys(data, KNOWN_APP_KEYS):
        issues.append(ConfigIssue(
            severity="info",
            file="app_settings.json",
            field=key,
            message=f"Ignored unknown setting key '{key}'.",
            action_taken="stripped on save",
        ))

    schema = int(data.get("schema_version", 0) or 0)
    if schema < APP_SCHEMA_VERSION:
        issues.append(ConfigIssue(
            severity="info",
            file="app_settings.json",
            field="schema_version",
            message=f"Migrated settings from schema {schema} to {APP_SCHEMA_VERSION}.",
            action_taken="schema_version updated",
        ))
        migrated = True
    elif schema > APP_SCHEMA_VERSION:
        issues.append(ConfigIssue(
            severity="warning",
            file="app_settings.json",
            field="schema_version",
            message=f"Settings schema {schema} is newer than app supports ({APP_SCHEMA_VERSION}).",
            action_taken="applied known fields only",
        ))

    before_payload = app_settings_to_payload(parse_app_settings(data))
    settings = parse_app_settings(data)
    _validate_app_paths(settings, issues)

    after_payload = app_settings_to_payload(settings)
    if after_payload != before_payload or schema < APP_SCHEMA_VERSION:
        save_app_settings(settings)
        if after_payload != before_payload and schema >= APP_SCHEMA_VERSION:
            migrated = True

    return settings, issues, backups, migrated


def _bootstrap_watcher_settings() -> tuple[WatcherSettings, list[ConfigIssue], list[Path], bool]:
    issues: list[ConfigIssue] = []
    backups: list[Path] = []
    migrated = False
    path = WATCHER_SETTINGS_FILE

    if not path.is_file():
        default = WatcherSettings(library_root=os.path.expanduser("~/Media_Library"))
        save_settings(default)
        issues.append(ConfigIssue(
            severity="info",
            file="watcher_settings.json",
            field="",
            message="Created default watcher settings.",
            action_taken="wrote defaults with schema_version",
        ))
        migrated = True
        return default, issues, backups, migrated

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("root must be a JSON object")
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        backups.append(_backup_file(path))
        issues.append(ConfigIssue(
            severity="error",
            file="watcher_settings.json",
            field="",
            message=f"Could not read settings file: {exc}",
            action_taken="restored defaults; backup saved",
        ))
        default = WatcherSettings(library_root=os.path.expanduser("~/Media_Library"))
        save_settings(default)
        return default, issues, backups, True

    for key in _unknown_keys(data, KNOWN_WATCHER_KEYS):
        issues.append(ConfigIssue(
            severity="info",
            file="watcher_settings.json",
            field=key,
            message=f"Ignored unknown setting key '{key}'.",
            action_taken="stripped on save",
        ))

    schema = int(data.get("schema_version", 0) or 0)
    if schema < WATCHER_SCHEMA_VERSION:
        issues.append(ConfigIssue(
            severity="info",
            file="watcher_settings.json",
            field="schema_version",
            message=f"Migrated settings from schema {schema} to {WATCHER_SCHEMA_VERSION}.",
            action_taken="schema_version updated",
        ))
        migrated = True
    elif schema > WATCHER_SCHEMA_VERSION:
        issues.append(ConfigIssue(
            severity="warning",
            file="watcher_settings.json",
            field="schema_version",
            message=f"Settings schema {schema} is newer than app supports ({WATCHER_SCHEMA_VERSION}).",
            action_taken="applied known fields only",
        ))

    raw_inbox = str(data.get("inbox_relative", "01_Inbox") or "")
    if raw_inbox and os.path.isabs(raw_inbox):
        issues.append(ConfigIssue(
            severity="warning",
            file="watcher_settings.json",
            field="inbox_relative",
            message=f"Inbox path must be relative to library root; reset from '{raw_inbox}'.",
            action_taken="normalized to 01_Inbox",
        ))

    action = str(data.get("action", "move") or "").lower()
    if action and action not in ("move", "copy"):
        issues.append(ConfigIssue(
            severity="warning",
            file="watcher_settings.json",
            field="action",
            message=f"Invalid action '{action}'; using 'move'.",
            action_taken="normalized action",
        ))

    before_payload = watcher_settings_to_payload(parse_watcher_settings(data))
    settings = parse_watcher_settings(data)
    _validate_watcher_paths(settings, issues)

    after_payload = watcher_settings_to_payload(settings)
    if after_payload != before_payload or schema < WATCHER_SCHEMA_VERSION:
        save_settings(settings)
        if after_payload != before_payload and schema >= WATCHER_SCHEMA_VERSION:
            migrated = True

    return settings, issues, backups, migrated


def bootstrap_config() -> BootstrapResult:
    """Load, validate, migrate, and persist both JSON configs. Call once before UI."""
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)

    app_settings, app_issues, app_backups, app_migrated = _bootstrap_app_settings()
    watcher_settings, watcher_issues, watcher_backups, watcher_migrated = _bootstrap_watcher_settings()

    set_app_settings_cache(app_settings)
    set_watcher_settings_cache(watcher_settings)

    issues = app_issues + watcher_issues
    backup_paths = app_backups + watcher_backups
    migrated = app_migrated or watcher_migrated

    if issues:
        for issue in issues:
            log_fn = logger.warning if issue.severity == "warning" else (
                logger.error if issue.severity == "error" else logger.info
            )
            log_fn(
                "Config [%s] %s.%s: %s (%s)",
                issue.severity, issue.file, issue.field, issue.message, issue.action_taken,
            )

    return BootstrapResult(
        app_settings=app_settings,
        watcher_settings=watcher_settings,
        issues=issues,
        migrated=migrated,
        backup_paths=backup_paths,
    )


def should_show_startup_dialog(result: BootstrapResult) -> bool:
    """True when user should see the startup issues dialog."""
    notable = [i for i in result.issues if i.severity in ("warning", "error")]
    if not notable:
        return False
    if result.app_settings.suppress_config_warnings:
        return any(i.severity == "error" for i in notable)
    return True


def show_startup_issues_dialog(parent, result: BootstrapResult) -> None:
    """Show a lightweight dialog for config warnings/errors on startup."""
    if not should_show_startup_dialog(result):
        return

    import customtkinter as ctk
    from app_settings import save_app_settings
    from theme import ERROR, APP_ACCENT, APP_BORDER, APP_DANGER_HOVER, APP_PRIMARY_TEXT, APP_TEXT_MUTED, TEXT_SECONDARY

    notable = [i for i in result.issues if i.severity in ("warning", "error")]

    dialog = ctk.CTkToplevel(parent)
    dialog.title("Settings checked on startup")
    dialog.geometry("560x420")
    dialog.transient(parent)
    dialog.grab_set()

    ctk.CTkLabel(
        dialog,
        text="Settings checked on startup",
        font=ctk.CTkFont(size=18, weight="bold"),
    ).pack(anchor="w", padx=20, pady=(16, 4))

    ctk.CTkLabel(
        dialog,
        text="The following issues were found while loading your configuration:",
        font=ctk.CTkFont(size=12),
        text_color=APP_TEXT_MUTED,
        wraplength=500,
        justify="left",
    ).pack(anchor="w", padx=20, pady=(0, 8))

    lines = []
    for issue in notable:
        prefix = issue.severity.upper()
        detail = issue.action_taken or issue.message
        lines.append(f"• [{prefix}] {issue.file}: {issue.message}")
        if issue.action_taken and issue.action_taken != issue.message:
            lines.append(f"  → {issue.action_taken}")

    box = ctk.CTkTextbox(dialog, height=220, wrap="word", font=("Segoe UI", 11))
    box.pack(fill="both", expand=True, padx=20, pady=(0, 8))
    box.insert("1.0", "\n".join(lines))
    box.configure(state="disabled")

    suppress_var = ctk.BooleanVar(value=False)
    has_warnings_only = all(i.severity == "warning" for i in notable)
    if has_warnings_only:
        ctk.CTkCheckBox(
            dialog,
            text="Don't show again for warnings",
            variable=suppress_var,
        ).pack(anchor="w", padx=20, pady=(0, 8))

    btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
    btn_row.pack(fill="x", padx=20, pady=(0, 16))

    def _open_folder():
        folder = str(SETTINGS_DIR)
        if os.name == "nt":
            os.startfile(folder)  # type: ignore[attr-defined]
        else:
            import subprocess
            subprocess.Popen(["xdg-open", folder])

    def _close():
        if suppress_var.get():
            updated = result.app_settings
            updated.suppress_config_warnings = True
            save_app_settings(updated)
        dialog.destroy()

    ctk.CTkButton(
        btn_row, text="Open settings folder", width=160,
        fg_color="transparent", border_width=1, border_color=APP_BORDER,
        command=_open_folder,
    ).pack(side="left")
    ctk.CTkButton(
        btn_row, text="OK", width=100,
        fg_color=APP_ACCENT, text_color=APP_PRIMARY_TEXT,
        command=_close,
    ).pack(side="right")

    dialog.protocol("WM_DELETE_WINDOW", _close)


def should_show_ffmpeg_dialog(settings: AppSettings) -> bool:
    """One-time warning when ffmpeg/ffprobe are missing from PATH."""
    if settings.suppress_ffmpeg_warning:
        return False
    from video_thumbs import ffmpeg_available
    return not ffmpeg_available()


def show_ffmpeg_missing_dialog(parent, settings: AppSettings) -> None:
    """Inform user that video features need ffmpeg on PATH."""
    if not should_show_ffmpeg_dialog(settings):
        return

    import customtkinter as ctk
    from app_settings import save_app_settings
    from theme import ERROR, APP_ACCENT, APP_BORDER, APP_DANGER_HOVER, APP_PRIMARY_TEXT, APP_TEXT_MUTED, TEXT_SECONDARY

    dialog = ctk.CTkToplevel(parent)
    dialog.title("ffmpeg not found")
    dialog.geometry("520x300")
    dialog.transient(parent)
    dialog.grab_set()

    ctk.CTkLabel(
        dialog,
        text="Video features need ffmpeg",
        font=ctk.CTkFont(size=18, weight="bold"),
    ).pack(anchor="w", padx=20, pady=(16, 4))

    ctk.CTkLabel(
        dialog,
        text=(
            "Video duplicate detection, thumbnails, and inline playback require "
            "ffmpeg and ffprobe on your system PATH.\n\n"
            "Download: https://ffmpeg.org/download.html\n"
            "After installing, restart Photo Organizer."
        ),
        font=ctk.CTkFont(size=12),
        text_color=APP_TEXT_MUTED,
        wraplength=460,
        justify="left",
    ).pack(anchor="w", padx=20, pady=(0, 12))

    suppress_var = ctk.BooleanVar(value=False)
    ctk.CTkCheckBox(
        dialog,
        text="Don't show again",
        variable=suppress_var,
    ).pack(anchor="w", padx=20, pady=(0, 8))

    btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
    btn_row.pack(fill="x", padx=20, pady=(0, 16))

    def _open_url():
        import webbrowser
        webbrowser.open("https://ffmpeg.org/download.html")

    def _close():
        if suppress_var.get():
            updated = settings
            updated.suppress_ffmpeg_warning = True
            save_app_settings(updated)
        dialog.destroy()

    ctk.CTkButton(
        btn_row, text="Download ffmpeg", width=140,
        fg_color="transparent", border_width=1, border_color=APP_BORDER,
        command=_open_url,
    ).pack(side="left")
    ctk.CTkButton(
        btn_row, text="OK", width=100,
        fg_color=APP_ACCENT, text_color=APP_PRIMARY_TEXT,
        command=_close,
    ).pack(side="right")

    dialog.protocol("WM_DELETE_WINDOW", _close)
