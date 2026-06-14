"""Centralized keyboard shortcut binding and persistence."""
from __future__ import annotations

from typing import Callable, Optional

from keyboard_bindings import binding_variants, resolve_binding

Handler = Callable


class ShortcutManager:
    """Loads keyboard_shortcuts overrides and binds widgets to actions."""

    def __init__(self) -> None:
        self._entries: list[dict] = []

    def get(self, action: str, default: str = "") -> str:
        return resolve_binding(action) or default

    def bind(
        self,
        widget,
        action: str,
        default: str,
        callback: Handler,
        *,
        add: str = "+",
    ) -> None:
        self.unbind_action(widget, action)
        entry = {
            "widget": widget,
            "action": action,
            "default": default,
            "callback": callback,
            "add": add,
            "bound": [],
        }
        self._entries.append(entry)
        self._apply_entry(entry)

    def unbind_action(self, widget, action: str) -> None:
        for i in range(len(self._entries) - 1, -1, -1):
            entry = self._entries[i]
            if entry["widget"] is widget and entry["action"] == action:
                self._unbind_entry(entry)
                self._entries.pop(i)

    def unbind_actions(self, widget, actions: list[str]) -> None:
        for action in actions:
            self.unbind_action(widget, action)

    def rebind_all(self) -> None:
        for entry in self._entries:
            self._unbind_entry(entry)
            self._apply_entry(entry)

    def _apply_entry(self, entry: dict) -> None:
        seq = self.get(entry["action"], entry["default"])
        if not seq:
            return
        widget = entry["widget"]
        callback = entry["callback"]
        for variant in binding_variants(seq):
            widget.bind(variant, callback, add=entry["add"])
            entry["bound"].append((variant, callback))

    def _unbind_entry(self, entry: dict) -> None:
        widget = entry["widget"]
        for seq, handler in entry.get("bound", []):
            try:
                widget.unbind(seq, handler)
            except Exception:
                pass
        entry["bound"] = []
