"""
GPS extraction from EXIF and map helpers.
"""
from __future__ import annotations

import logging
import webbrowser
from typing import Optional

try:
    import piexif
    HAS_PIEXIF = True
except ImportError:
    HAS_PIEXIF = False

logger = logging.getLogger(__name__)


def _ratio_to_float(value) -> float:
    try:
        if isinstance(value, tuple) and len(value) == 2:
            num, den = value
            return float(num) / float(den) if den else 0.0
        return float(value)
    except (TypeError, ValueError, ZeroDivisionError):
        return 0.0


def gps_from_piexif_dict(exif_dict: dict) -> tuple[Optional[float], Optional[float]]:
    """Return (latitude, longitude) in decimal degrees, or (None, None)."""
    if not HAS_PIEXIF:
        return None, None
    gps = exif_dict.get("GPS") or {}
    if not gps:
        return None, None
    try:
        lat = gps.get(piexif.GPSIFD.GPSLatitude)
        lat_ref = _decode_ref(gps.get(piexif.GPSIFD.GPSLatitudeRef))
        lon = gps.get(piexif.GPSIFD.GPSLongitude)
        lon_ref = _decode_ref(gps.get(piexif.GPSIFD.GPSLongitudeRef))
        if not lat or not lon:
            return None, None
        lat_d = _ratio_to_float(lat[0]) + _ratio_to_float(lat[1]) / 60 + _ratio_to_float(lat[2]) / 3600
        lon_d = _ratio_to_float(lon[0]) + _ratio_to_float(lon[1]) / 60 + _ratio_to_float(lon[2]) / 3600
        if lat_ref in ("S", "s"):
            lat_d = -lat_d
        if lon_ref in ("W", "w"):
            lon_d = -lon_d
        return lat_d, lon_d
    except Exception as exc:
        logger.debug("GPS parse failed: %s", exc)
        return None, None


def _decode_ref(raw) -> str:
    if raw is None:
        return ""
    if isinstance(raw, bytes):
        return raw.decode("ascii", errors="ignore")
    return str(raw)


def read_gps_from_image(path: str) -> tuple[Optional[float], Optional[float]]:
    if not HAS_PIEXIF:
        return None, None
    try:
        exif_dict = piexif.load(path)
        return gps_from_piexif_dict(exif_dict)
    except Exception:
        return None, None


def osm_url(lat: float, lon: float, zoom: int = 15) -> str:
    return f"https://www.openstreetmap.org/?mlat={lat:.6f}&mlon={lon:.6f}#map={zoom}/{lat:.6f}/{lon:.6f}"


def open_in_browser(lat: float, lon: float) -> None:
    webbrowser.open(osm_url(lat, lon))
