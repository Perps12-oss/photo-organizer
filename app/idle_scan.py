"""
Detect system idle state and schedule background duplicate scans.
Windows: uses GetLastInputInfo (no extra dependencies).
"""
from __future__ import annotations

import logging
import os
import sys
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)

POLL_INTERVAL_MS = 60_000  # check once per minute


def get_user_idle_seconds() -> float:
    """Seconds since last keyboard/mouse input. 0 if unknown."""
    if sys.platform != "win32":
        return 0.0
    try:
        import ctypes
        from ctypes import wintypes

        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
            return 0.0
        tick = ctypes.windll.kernel32.GetTickCount()
        return max(0.0, (tick - lii.dwTime) / 1000.0)
    except Exception as e:
        logger.debug("Idle detection unavailable: %s", e)
        return 0.0


def is_workstation_locked() -> bool:
    """True when the Windows session appears locked (screensaver / lock screen)."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if hwnd == 0:
            return True
        return False
    except Exception:
        return False


def is_on_battery() -> Optional[bool]:
    """True on battery, False on AC, None if psutil unavailable."""
    try:
        import psutil
        battery = psutil.sensors_battery()
        if battery is None:
            return None
        return not battery.power_plugged
    except Exception:
        return None


def cpu_usage_percent() -> Optional[float]:
    try:
        import psutil
        return float(psutil.cpu_percent(interval=0.1))
    except Exception:
        return None


def is_system_idle(
    idle_minutes: int,
    app_minimized: bool = False,
    *,
    only_when_locked: bool = False,
    skip_on_battery: bool = False,
    max_cpu_percent: Optional[int] = None,
) -> bool:
    """Idle if no input for N minutes, app is in tray, or session has no foreground window."""
    if skip_on_battery:
        on_battery = is_on_battery()
        if on_battery is True:
            return False
    if max_cpu_percent is not None:
        usage = cpu_usage_percent()
        if usage is not None and usage > max_cpu_percent:
            return False
    if only_when_locked:
        return is_workstation_locked()
    if app_minimized:
        return True
    if is_workstation_locked():
        return True
    threshold = max(1, idle_minutes) * 60
    return get_user_idle_seconds() >= threshold


class IdleDuplicateScanner:
    """Polls for idle time and triggers a silent recent duplicate scan."""

    def __init__(
        self,
        root,
        should_scan: Callable[[], bool],
        start_scan: Callable[[], None],
        is_scan_running: Callable[[], bool],
        get_cooldown_remaining: Callable[[], float],
    ):
        self.root = root
        self.should_scan = should_scan
        self.start_scan = start_scan
        self.is_scan_running = is_scan_running
        self.get_cooldown_remaining = get_cooldown_remaining
        self._poll_job: Optional[int] = None
        self._enabled = False

    def set_enabled(self, enabled: bool):
        self._enabled = enabled
        if enabled:
            self._schedule_poll()
        elif self._poll_job:
            self.root.after_cancel(self._poll_job)
            self._poll_job = None

    def _schedule_poll(self):
        if self._poll_job:
            self.root.after_cancel(self._poll_job)
        self._poll_job = self.root.after(POLL_INTERVAL_MS, self._tick)

    def _tick(self):
        self._poll_job = None
        if not self._enabled:
            return
        try:
            if self.should_scan() and not self.is_scan_running():
                remaining = self.get_cooldown_remaining()
                if remaining <= 0:
                    logger.info("Idle duplicate scan starting (system idle)")
                    self.start_scan()
        except Exception as e:
            logger.warning("Idle scan tick failed: %s", e)
        finally:
            if self._enabled:
                self._schedule_poll()


def resolve_scan_folder(configured: str) -> str:
    """Folder for idle scan — configured path or library root."""
    path = (configured or "").strip()
    if path and os.path.isdir(path):
        return path
    try:
        from inbox_watcher import load_settings
        root = load_settings().library_root.strip()
        if root and os.path.isdir(root):
            return root
    except Exception:
        pass
    return path
