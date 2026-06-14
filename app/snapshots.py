"""
Folder/file snapshots for rollback before bulk delete or organize.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

SNAPSHOT_ROOT = Path(os.environ.get("APPDATA", os.path.expanduser("~"))) / "PhotoOrganizer" / "snapshots"


@dataclass
class SnapshotInfo:
    id: str
    label: str
    created: str
    file_count: int
    bytes_total: int


def _snapshot_dir(snap_id: str) -> Path:
    return SNAPSHOT_ROOT / snap_id


def list_snapshots() -> list[SnapshotInfo]:
    if not SNAPSHOT_ROOT.is_dir():
        return []
    result: list[SnapshotInfo] = []
    for child in sorted(SNAPSHOT_ROOT.iterdir(), reverse=True):
        if not child.is_dir():
            continue
        manifest = child / "manifest.json"
        if not manifest.is_file():
            continue
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            result.append(
                SnapshotInfo(
                    id=data.get("id", child.name),
                    label=data.get("label", child.name),
                    created=data.get("created", ""),
                    file_count=int(data.get("file_count", 0)),
                    bytes_total=int(data.get("bytes_total", 0)),
                )
            )
        except (json.JSONDecodeError, OSError, TypeError):
            continue
    return result


def create_snapshot(
    label: str,
    paths: list[str],
    on_progress: Optional[Callable[[int, int, str], None]] = None,
) -> SnapshotInfo:
    SNAPSHOT_ROOT.mkdir(parents=True, exist_ok=True)
    snap_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
    root = _snapshot_dir(snap_id)
    files_dir = root / "files"
    files_dir.mkdir(parents=True)

    entries: list[dict] = []
    total_bytes = 0
    valid = [p for p in paths if os.path.isfile(p)]
    for i, src in enumerate(valid, start=1):
        if on_progress:
            on_progress(i, len(valid), src)
        base = os.path.basename(src)
        dest_name = base
        n = 1
        while (files_dir / dest_name).exists():
            stem, ext = os.path.splitext(base)
            dest_name = f"{stem}_{n}{ext}"
            n += 1
        dest = files_dir / dest_name
        shutil.copy2(src, dest)
        size = dest.stat().st_size
        total_bytes += size
        entries.append({
            "original": os.path.abspath(src),
            "stored": dest_name,
            "size": size,
        })

    created = datetime.now().isoformat(timespec="seconds")
    manifest = {
        "id": snap_id,
        "label": label or snap_id,
        "created": created,
        "file_count": len(entries),
        "bytes_total": total_bytes,
        "files": entries,
    }
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return SnapshotInfo(
        id=snap_id,
        label=manifest["label"],
        created=created,
        file_count=len(entries),
        bytes_total=total_bytes,
    )


def restore_snapshot(
    snap_id: str,
    overwrite: bool = False,
    on_progress: Optional[Callable[[int, int, str], None]] = None,
) -> tuple[int, list[str]]:
    root = _snapshot_dir(snap_id)
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        return 0, ["Snapshot not found"]
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = data.get("files", [])
    restored = 0
    errors: list[str] = []
    files_dir = root / "files"
    for i, entry in enumerate(files, start=1):
        original = entry.get("original", "")
        stored = entry.get("stored", "")
        src = files_dir / stored
        if on_progress:
            on_progress(i, len(files), original)
        if not src.is_file():
            errors.append(f"Missing backup: {stored}")
            continue
        if os.path.exists(original) and not overwrite:
            errors.append(f"Exists (skipped): {os.path.basename(original)}")
            continue
        try:
            os.makedirs(os.path.dirname(original) or ".", exist_ok=True)
            shutil.copy2(src, original)
            restored += 1
        except OSError as exc:
            errors.append(f"{os.path.basename(original)}: {exc}")
    return restored, errors


def delete_snapshot(snap_id: str) -> bool:
    root = _snapshot_dir(snap_id)
    if not root.is_dir():
        return False
    try:
        shutil.rmtree(root)
        return True
    except OSError as exc:
        logger.warning("delete_snapshot failed: %s", exc)
        return False


def create_folder_snapshot(
    folder: str,
    label: str = "",
    recursive: bool = True,
    on_progress: Optional[Callable[[int, int, str], None]] = None,
) -> SnapshotInfo:
    """Full-folder snapshot wizard helper — backs up all files under folder."""
    paths: list[str] = []
    if not os.path.isdir(folder):
        return create_snapshot(label or "empty", [], on_progress=on_progress)
    for dirpath, _, filenames in os.walk(folder):
        if not recursive and os.path.abspath(dirpath) != os.path.abspath(folder):
            continue
        for name in filenames:
            paths.append(os.path.join(dirpath, name))
    return create_snapshot(label or os.path.basename(folder) or "folder", paths, on_progress=on_progress)
