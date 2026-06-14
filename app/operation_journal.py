"""
File-operation journal with quarantine-based delete undo and redo.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

logger = logging.getLogger(__name__)

JOURNAL_DIR = Path(os.environ.get("APPDATA", os.path.expanduser("~"))) / "PhotoOrganizer"
JOURNAL_FILE = JOURNAL_DIR / "operation_journal.json"
QUARANTINE_DIR = JOURNAL_DIR / "quarantine"

ActionType = Literal["move", "copy", "delete", "rename"]


@dataclass
class JournalEntry:
    action: ActionType
    source: str
    destination: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


@dataclass
class OperationJournal:
    entries: list[JournalEntry] = field(default_factory=list)
    redo_stack: list[JournalEntry] = field(default_factory=list)
    max_entries: int = 200

    def record(self, action: ActionType, source: str, destination: str = "") -> None:
        self.entries.append(JournalEntry(action=action, source=source, destination=destination))
        self.redo_stack.clear()
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries :]
        self.save()

    def record_delete(self, path: str) -> tuple[bool, str]:
        """Move file to quarantine instead of permanent delete; journal for undo."""
        if not os.path.isfile(path):
            return False, "File not found"
        try:
            quarantine_path = _move_to_quarantine(path)
        except OSError as exc:
            return False, str(exc)
        self.record("delete", path, quarantine_path)
        return True, quarantine_path

    def undo_last(self) -> tuple[bool, str]:
        if not self.entries:
            return False, "Nothing to undo"
        entry = self.entries.pop()
        ok, msg = _reverse_entry(entry)
        if ok:
            self.redo_stack.append(entry)
            self.save()
            return True, msg
        self.entries.append(entry)
        self.save()
        return False, msg

    def redo_last(self) -> tuple[bool, str]:
        if not self.redo_stack:
            return False, "Nothing to redo"
        entry = self.redo_stack.pop()
        ok, msg = _reapply_entry(entry)
        if ok:
            self.entries.append(entry)
            self.save()
            return True, msg
        self.redo_stack.append(entry)
        return False, msg

    def save(self) -> None:
        JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "entries": [asdict(e) for e in self.entries],
            "redo_stack": [asdict(e) for e in self.redo_stack],
        }
        tmp = JOURNAL_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp, JOURNAL_FILE)

    @classmethod
    def load(cls) -> "OperationJournal":
        if not JOURNAL_FILE.is_file():
            return cls()
        try:
            data = json.loads(JOURNAL_FILE.read_text(encoding="utf-8"))
            entries = [JournalEntry(**e) for e in data.get("entries", [])]
            redo = [JournalEntry(**e) for e in data.get("redo_stack", [])]
            return cls(entries=entries, redo_stack=redo)
        except (json.JSONDecodeError, OSError, TypeError) as exc:
            logger.warning("Could not load operation journal: %s", exc)
            return cls()


def _move_to_quarantine(path: str) -> str:
    QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
    folder = QUARANTINE_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    folder.mkdir(parents=True)
    dest = folder / os.path.basename(path)
    if dest.exists():
        dest = folder / f"{uuid.uuid4().hex[:6]}_{os.path.basename(path)}"
    shutil.move(path, dest)
    manifest = {"original": os.path.abspath(path), "quarantine": str(dest.resolve())}
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return str(dest.resolve())


def _restore_from_quarantine(entry: JournalEntry) -> tuple[bool, str]:
    quarantine = entry.destination
    original = entry.source
    if not quarantine or not os.path.isfile(quarantine):
        return False, "Quarantined file missing — cannot restore"
    os.makedirs(os.path.dirname(original) or ".", exist_ok=True)
    if os.path.exists(original):
        return False, f"Cannot restore — file already exists: {os.path.basename(original)}"
    shutil.move(quarantine, original)
    _cleanup_quarantine_folder(quarantine)
    return True, f"Restored {os.path.basename(original)}"


def _cleanup_quarantine_folder(quarantine_file: str) -> None:
    folder = Path(quarantine_file).parent
    try:
        if folder.is_dir() and folder.parent == QUARANTINE_DIR:
            for child in folder.iterdir():
                child.unlink(missing_ok=True)
            folder.rmdir()
    except OSError:
        pass


def _reverse_entry(entry: JournalEntry) -> tuple[bool, str]:
    try:
        if entry.action == "delete":
            return _restore_from_quarantine(entry)
        if entry.action == "move" and entry.destination and os.path.isfile(entry.destination):
            os.makedirs(os.path.dirname(entry.source) or ".", exist_ok=True)
            shutil.move(entry.destination, entry.source)
            return True, f"Restored {os.path.basename(entry.source)}"
        if entry.action == "copy" and entry.destination and os.path.isfile(entry.destination):
            os.remove(entry.destination)
            return True, f"Removed copy {os.path.basename(entry.destination)}"
        if entry.action == "rename" and entry.destination and os.path.isfile(entry.destination):
            os.rename(entry.destination, entry.source)
            return True, f"Renamed back to {os.path.basename(entry.source)}"
    except OSError as exc:
        return False, str(exc)
    return False, f"Cannot undo {entry.action}"


def _reapply_entry(entry: JournalEntry) -> tuple[bool, str]:
    try:
        if entry.action == "delete":
            if os.path.isfile(entry.source):
                quarantine_path = _move_to_quarantine(entry.source)
                entry.destination = quarantine_path
                return True, f"Deleted {os.path.basename(entry.source)} again"
            return False, "Original file not found for redo delete"
        if entry.action == "move" and entry.source and entry.destination:
            if os.path.isfile(entry.source):
                os.makedirs(os.path.dirname(entry.destination) or ".", exist_ok=True)
                shutil.move(entry.source, entry.destination)
                return True, f"Moved {os.path.basename(entry.source)} again"
        if entry.action == "copy" and entry.source and entry.destination:
            if os.path.isfile(entry.source):
                os.makedirs(os.path.dirname(entry.destination) or ".", exist_ok=True)
                shutil.copy2(entry.source, entry.destination)
                return True, f"Copied {os.path.basename(entry.source)} again"
        if entry.action == "rename" and entry.source and entry.destination:
            if os.path.isfile(entry.source):
                os.makedirs(os.path.dirname(entry.destination) or ".", exist_ok=True)
                os.rename(entry.source, entry.destination)
                return True, f"Renamed to {os.path.basename(entry.destination)} again"
    except OSError as exc:
        return False, str(exc)
    return False, f"Cannot redo {entry.action}"
