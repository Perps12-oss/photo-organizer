"""Minimal i18n stub — English default with JSON locale foundation."""
from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_LOCALE_DIR = Path(__file__).resolve().parent
_DEFAULT_LOCALE = "en"
_cache: dict[str, dict[str, str]] = {}
_current_locale = _DEFAULT_LOCALE


def set_locale(code: str) -> None:
    global _current_locale
    _current_locale = code or _DEFAULT_LOCALE
    _cache.pop(_current_locale, None)


def get_locale() -> str:
    return _current_locale


def _load_locale(code: str) -> dict[str, str]:
    if code in _cache:
        return _cache[code]
    path = _LOCALE_DIR / f"{code}.json"
    if not path.is_file():
        _cache[code] = {}
        return _cache[code]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        strings = data.get("strings", data) if isinstance(data, dict) else {}
        _cache[code] = {str(k): str(v) for k, v in strings.items()} if isinstance(strings, dict) else {}
    except (json.JSONDecodeError, OSError) as exc:
        logger.debug("Locale load failed for %s: %s", code, exc)
        _cache[code] = {}
    return _cache[code]


def t(key: str, locale: str | None = None, **kwargs) -> str:
    """Translate key; falls back to key itself when missing."""
    loc = locale or _current_locale
    text = _load_locale(loc).get(key) or _load_locale(_DEFAULT_LOCALE).get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, ValueError):
            return text
    return text
