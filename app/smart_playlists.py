"""
Smart playlists — saved filter rules that auto-update (T2 scaffold).
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

PLAYLISTS_FILE = Path(os.environ.get("APPDATA", os.path.expanduser("~"))) / "PhotoOrganizer" / "smart_playlists.json"


@dataclass
class SmartPlaylist:
    name: str
    min_rating: int = 0
    tag: str = ""
    search: str = ""
    match_all_tags: bool = False
    gallery_sort: str = ""
    date_from: str = ""
    date_to: str = ""


@dataclass
class PlaylistStore:
    playlists: list[SmartPlaylist] = field(default_factory=list)

    def save(self) -> None:
        PLAYLISTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {"playlists": [asdict(p) for p in self.playlists]}
        tmp = PLAYLISTS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp, PLAYLISTS_FILE)

    @classmethod
    def load(cls) -> "PlaylistStore":
        if not PLAYLISTS_FILE.is_file():
            return cls()
        try:
            data = json.loads(PLAYLISTS_FILE.read_text(encoding="utf-8"))
            playlists = [SmartPlaylist(**p) for p in data.get("playlists", [])]
            return cls(playlists=playlists)
        except (json.JSONDecodeError, OSError, TypeError):
            return cls()
