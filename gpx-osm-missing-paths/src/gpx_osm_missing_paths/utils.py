"""Small pure geo/text helpers shared across the pipeline."""

from __future__ import annotations

import json
import math
import re
import tempfile
import unicodedata
from pathlib import Path
from typing import Any

from shapely.geometry import LineString, Polygon
from shapely.geometry.base import BaseGeometry

EARTH_RADIUS_M = 6_371_000.0


def load_osmconvert_poly(path: Path) -> Polygon:
    """Parse an osmconvert ``.poly`` boundary into a WGS84 shapely Polygon.

    Format: header line(s), then one or more rings of ``lon lat`` rows separated
    by ``END`` (final ``END`` closes the file). Only the first outer ring is used.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    coords: list[tuple[float, float]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.upper() == "END":
            if coords:
                break
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        try:
            lon, lat = float(parts[0]), float(parts[1])
        except ValueError:
            continue
        coords.append((lon, lat))
    if len(coords) < 3:
        raise ValueError(f"No usable ring in poly file: {path}")
    if coords[0] != coords[-1]:
        coords.append(coords[0])
    return Polygon(coords)


def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Great-circle distance in meters between two WGS84 points."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def line_length_m(line: LineString) -> float:
    """Sum of haversine segment lengths for a WGS84 LineString."""
    coords = list(line.coords)
    return sum(
        haversine_m(coords[i][0], coords[i][1], coords[i + 1][0], coords[i + 1][1])
        for i in range(len(coords) - 1)
    )


def bearing_deg(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Initial compass bearing in degrees [0, 360) from point 1 to point 2."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)
    x = math.sin(dlambda) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda)
    return (math.degrees(math.atan2(x, y)) + 360.0) % 360.0


def line_bearing_deg(line: LineString) -> float:
    """Bearing of a LineString from its first to its last coordinate."""
    coords = list(line.coords)
    return bearing_deg(coords[0][0], coords[0][1], coords[-1][0], coords[-1][1])


def bearing_diff_deg(a: float, b: float) -> float:
    """Smallest absolute angle between two bearings, treating a path and its
    reverse as the same direction (0-180 degrees)."""
    diff = abs(a - b) % 360.0
    diff = min(diff, 360.0 - diff)
    return min(diff, 180.0 - diff) if diff > 90.0 else diff


def utm_epsg_for(lon: float, lat: float) -> int:
    """Best-fit UTM EPSG code for a WGS84 point (used for meter-accurate ops)."""
    zone = int((lon + 180.0) // 6.0) + 1
    return (32600 if lat >= 0 else 32700) + zone


_SLUG_RE = re.compile(r"[^a-z0-9]+")
# Đ/đ (D/d with stroke) has no NFKD decomposition to plain ASCII "D"/"d" — map explicitly
# or Vietnamese street names like "Đường" silently lose their first letter when slugified.
_MANUAL_TRANSLITERATIONS = {"Đ": "D", "đ": "d"}


def slugify(text: str, max_length: int = 80) -> str:
    """Filesystem/URL-safe ASCII slug. Strips Vietnamese diacritics, keeps meaning."""
    for char, replacement in _MANUAL_TRANSLITERATIONS.items():
        text = text.replace(char, replacement)
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = _SLUG_RE.sub("_", ascii_text).strip("_")
    return slug[:max_length].strip("_") or "path"


def atomic_write_json(path: Path, data: dict[str, Any] | list[Any]) -> None:
    """Write JSON atomically (tmp file + rename) so partial writes never land."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", dir=path.parent, suffix=".tmp", delete=False, encoding="utf-8"
    ) as tmp:
        json.dump(data, tmp, ensure_ascii=False, indent=2, default=str)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def geometry_bbox(geom: BaseGeometry) -> tuple[float, float, float, float]:
    """(minx, miny, maxx, maxy) bounding box of a shapely geometry."""
    minx, miny, maxx, maxy = geom.bounds
    return (minx, miny, maxx, maxy)
