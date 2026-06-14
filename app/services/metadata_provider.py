"""Centralized metadata cache with background warm-up worker."""
from __future__ import annotations

import logging
import os
import queue
import threading
from typing import Callable, Optional

from metadata_tools import ImageMetadata, read_metadata, scan_gallery_metadata

logger = logging.getLogger(__name__)


class MetadataProvider:
    """Thread-safe metadata cache with lazy background fill."""

    def __init__(self) -> None:
        self._cache: dict[str, ImageMetadata] = {}
        self._lock = threading.Lock()
        self._queue: queue.Queue[Optional[str]] = queue.Queue()
        self._worker: Optional[threading.Thread] = None
        self._on_update: list[Callable[[str, ImageMetadata], None]] = []
        self._stop = threading.Event()

    def get(self, path: str, *, blocking: bool = False) -> ImageMetadata:
        """Return cached metadata. Non-blocking: placeholder + background queue on miss."""
        with self._lock:
            cached = self._cache.get(path)
        if cached is not None:
            return cached
        if blocking:
            return self.get_sync(path)
        self._enqueue_paths([path])
        return ImageMetadata(filepath=path, filename=os.path.basename(path))

    def get_sync(self, path: str) -> ImageMetadata:
        """Blocking read — use for save/write paths only."""
        with self._lock:
            cached = self._cache.get(path)
        if cached is not None:
            return cached
        meta = read_metadata(path)
        self.put(path, meta)
        return meta

    def peek(self, path: str) -> Optional[ImageMetadata]:
        with self._lock:
            return self._cache.get(path)

    def put(self, path: str, meta: ImageMetadata) -> None:
        with self._lock:
            self._cache[path] = meta
        for cb in self._on_update:
            try:
                cb(path, meta)
            except Exception as exc:
                logger.debug("Metadata update callback failed: %s", exc)

    def cache_snapshot(self) -> dict[str, ImageMetadata]:
        with self._lock:
            return dict(self._cache)

    def on_update(self, callback: Callable[[str, ImageMetadata], None]) -> None:
        self._on_update.append(callback)

    def warm_cache(
        self,
        folder: str,
        paths: Optional[list[str]] = None,
        recursive: bool = False,
        *,
        background: bool = True,
    ) -> None:
        """Pre-fill cache for a folder. Returns immediately; worker fills progressively."""
        if paths is None:
            scanned = scan_gallery_metadata(folder, recursive=recursive)
            with self._lock:
                self._cache.update(scanned)
            paths = list(scanned.keys())

        missing = []
        with self._lock:
            for path in paths:
                if path not in self._cache:
                    missing.append(path)

        if not missing:
            return

        if background:
            self._enqueue_paths(missing)
        else:
            for path in missing:
                self.put(path, read_metadata(path))

    def _enqueue_paths(self, paths: list[str]) -> None:
        for path in paths:
            self._queue.put(path)
        self._ensure_worker()

    def _ensure_worker(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        self._stop.clear()
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()

    def _worker_loop(self) -> None:
        while not self._stop.is_set():
            try:
                path = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if path is None:
                break
            if not path or not os.path.isfile(path):
                continue
            with self._lock:
                if path in self._cache:
                    continue
            try:
                meta = read_metadata(path)
                self.put(path, meta)
            except Exception as exc:
                logger.debug("Metadata read failed for %s: %s", path, exc)

    def shutdown(self) -> None:
        self._stop.set()
        self._queue.put(None)
