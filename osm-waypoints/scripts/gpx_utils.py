"""Utilities for reading GPX tracks and building extract polygons."""

from __future__ import annotations

from pathlib import Path

import gpxpy
import numpy as np
import pyproj
from shapely.geometry import MultiPoint, Polygon
from shapely.ops import transform


def load_track_points(gpx_dir: Path) -> list[tuple[float, float]]:
    """Load all track and route points from GPX files in a directory."""
    points: list[tuple[float, float]] = []

    for gpx_path in sorted(gpx_dir.glob("*.gpx")):
        with gpx_path.open() as handle:
            gpx = gpxpy.parse(handle)

        for track in gpx.tracks:
            for segment in track.segments:
                for point in segment.points:
                    points.append((point.longitude, point.latitude))

        for route in gpx.routes:
            for point in route.points:
                points.append((point.longitude, point.latitude))

        for waypoint in gpx.waypoints:
            points.append((waypoint.longitude, waypoint.latitude))

    if not points:
        raise ValueError(f"No coordinates found in GPX files under {gpx_dir}")

    return points


def _utm_transformers(
    points: list[tuple[float, float]],
) -> tuple[pyproj.Transformer, pyproj.Transformer]:
    min_lon = min(lon for lon, _ in points)
    max_lon = max(lon for lon, _ in points)
    min_lat = min(lat for _, lat in points)
    max_lat = max(lat for _, lat in points)

    center_lat = (min_lat + max_lat) / 2
    center_lon = (min_lon + max_lon) / 2

    zone = int((center_lon + 180) / 6) + 1
    hemisphere = "south" if center_lat < 0 else "north"
    utm_crs = f"+proj=utm +zone={zone} +{hemisphere} +datum=WGS84 +units=m +no_defs"

    to_utm = pyproj.Transformer.from_crs("EPSG:4326", utm_crs, always_xy=True)
    to_wgs = pyproj.Transformer.from_crs(utm_crs, "EPSG:4326", always_xy=True)
    return to_utm, to_wgs


def compute_convex_polygon_with_buffer(
    points: list[tuple[float, float]], buffer_km: float
) -> Polygon:
    """Return a buffered convex hull polygon around all GPX coordinates."""
    to_utm, to_wgs = _utm_transformers(points)

    lons = np.fromiter((lon for lon, _ in points), dtype=np.float64)
    lats = np.fromiter((lat for _, lat in points), dtype=np.float64)
    xs, ys = to_utm.transform(lons, lats)

    hull_utm = MultiPoint(np.column_stack((xs, ys))).convex_hull
    buffered_utm = hull_utm.buffer(buffer_km * 1000)
    polygon_wgs = transform(to_wgs.transform, buffered_utm)

    if polygon_wgs.is_empty or polygon_wgs.geom_type != "Polygon":
        raise ValueError("Failed to build a buffered convex hull polygon")

    return polygon_wgs