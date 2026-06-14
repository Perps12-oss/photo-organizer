"""Lightweight publish/subscribe event bus for decoupled view communication."""
from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

Handler = Callable[..., None]


class EventBus:
    def __init__(self) -> None:
        self._subs: dict[str, list[Handler]] = {}

    def subscribe(self, event: str, handler: Handler) -> None:
        self._subs.setdefault(event, []).append(handler)

    def unsubscribe(self, event: str, handler: Handler) -> None:
        handlers = self._subs.get(event, [])
        if handler in handlers:
            handlers.remove(handler)

    def publish(self, event: str, **payload: Any) -> None:
        for handler in list(self._subs.get(event, [])):
            try:
                handler(**payload)
            except Exception as exc:
                logger.warning("Event handler failed for %s: %s", event, exc)
