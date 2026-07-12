"""The only module that touches gpxpy. Turns raw GPX files into clean GPXSegment objects."""

from __future__ import annotations

import gzip
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import geopandas as gpd
import gpxpy
import gpxpy.gpx
import pandas as pd
from pyproj import Transformer
from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry

from gpx_osm_missing_paths.config import Settings
from gpx_osm_missing_paths.models import GPXSegment
from gpx_osm_missing_paths.utils import (
    geometry_bbox,
    haversine_m,
    line_length_m,
    load_osmconvert_poly,
    utm_epsg_for,
)

# Generous Vietnam bounding box; points outside are almost certainly bad fixes
# (cold-start GPS jumps to 0,0 or another continent). Not a hard city boundary.
VIETNAM_BBOX = (102.0, 8.0, 110.0, 24.0)

DUPLICATE_POINT_TOLERANCE_M = 0.5


@dataclass
class ProcessSummary:
    """Rich-printable counters for ``gpx-osm process``."""

    files_seen: int = 0
    files_failed: int = 0
    segments_kept: int = 0
    segments_dropped_short: int = 0
    segments_dropped_empty: int = 0
    segments_dropped_outside_city: int = 0
    total_km: float = 0.0


def discover_gpx_files(gpx_dir: Path) -> list[Path]:
    """Recursively find ``*.gpx`` and ``*.gpx.gz`` under ``gpx_dir``."""
    if not gpx_dir.is_dir():
        return []
    files = sorted(gpx_dir.rglob("*.gpx")) + sorted(gpx_dir.rglob("*.gpx.gz"))
    return files


def _read_text(path: Path) -> str:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    return path.read_text(encoding="utf-8", errors="replace")


def _in_bbox(lon: float, lat: float, bbox: tuple[float, float, float, float]) -> bool:
    minx, miny, maxx, maxy = bbox
    return minx <= lon <= maxx and miny <= lat <= maxy


def _dedupe_points(
    points: list[tuple[float, float, datetime | None]],
) -> list[tuple[float, float, datetime | None]]:
    if not points:
        return points
    kept = [points[0]]
    for lon, lat, ts in points[1:]:
        plon, plat, _ = kept[-1]
        if haversine_m(plon, plat, lon, lat) >= DUPLICATE_POINT_TOLERANCE_M:
            kept.append((lon, lat, ts))
    return kept


def _split_points_by_distance(
    points: list[tuple[float, float, datetime | None]], chunk_length_m: float
) -> list[list[tuple[float, float, datetime | None]]]:
    """Cut a long cleaned trace into ~``chunk_length_m`` pieces (street-sized, not run-sized).

    Consecutive chunks share their boundary point so there's no gap between them.
    """
    if len(points) < 2:
        return [points] if points else []

    chunks: list[list[tuple[float, float, datetime | None]]] = [[points[0]]]
    accumulated = 0.0
    for prev, curr in zip(points, points[1:], strict=False):
        accumulated += haversine_m(prev[0], prev[1], curr[0], curr[1])
        chunks[-1].append(curr)
        if accumulated >= chunk_length_m:
            chunks.append([curr])
            accumulated = 0.0
    if len(chunks[-1]) < 2:
        chunks.pop()
    return chunks


def _simplify_line(line: LineString, tolerance_m: float) -> LineString:
    """Douglas-Peucker simplify in meter-accurate local UTM, returned in EPSG:4326."""
    lon0, lat0 = line.coords[0][0], line.coords[0][1]
    epsg = utm_epsg_for(lon0, lat0)
    to_utm = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
    to_wgs84 = Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326", always_xy=True)

    utm_coords = [to_utm.transform(x, y) for x, y in line.coords]
    simplified = LineString(utm_coords).simplify(tolerance_m, preserve_topology=False)
    wgs84_coords = [to_wgs84.transform(x, y) for x, y in simplified.coords]
    return LineString(wgs84_coords)


def _segment_from_chunk(
    chunk: list[tuple[float, float, datetime | None]],
    source_file: Path,
    original_file: str,
    track_index: int,
    segment_index: int,
    chunk_index: int,
    settings: Settings,
) -> GPXSegment | None:
    if len(chunk) < 2:
        return None

    raw_line = LineString([(lon, lat) for lon, lat, _ in chunk])
    line = _simplify_line(raw_line, settings.simplify_tolerance_m)
    if len(line.coords) < 2:
        return None

    length_m = line_length_m(line)
    if length_m < settings.min_segment_length_m:
        return None

    start_time = next((ts for _, _, ts in chunk if ts is not None), None)
    end_time = next((ts for _, _, ts in reversed(chunk) if ts is not None), None)

    segment_id = f"{original_file}#t{track_index}s{segment_index}c{chunk_index}"
    return GPXSegment(
        segment_id=segment_id,
        source_file=source_file,
        original_file=original_file,
        track_index=track_index,
        segment_index=segment_index,
        chunk_index=chunk_index,
        geometry=line,
        length_m=length_m,
        num_points=len(chunk),
        start_time=start_time,
        end_time=end_time,
        bbox=geometry_bbox(line),
    )


def _segments_from_points(
    points: list[tuple[float, float, datetime | None]],
    source_file: Path,
    original_file: str,
    track_index: int,
    segment_index: int,
    settings: Settings,
) -> list[GPXSegment]:
    """Clean one ``<trkseg>``'s points and cut the result into street-sized chunks."""
    valid = [(lon, lat, ts) for lon, lat, ts in points if _in_bbox(lon, lat, VIETNAM_BBOX)]
    deduped = _dedupe_points(valid)
    if len(deduped) < 2:
        return []

    chunks = _split_points_by_distance(deduped, settings.segment_chunk_length_m)
    segments = []
    for chunk_index, chunk in enumerate(chunks):
        segment = _segment_from_chunk(
            chunk, source_file, original_file, track_index, segment_index, chunk_index, settings
        )
        if segment is not None:
            segments.append(segment)
    return segments


def parse_gpx_file(
    path: Path, gpx_dir: Path, settings: Settings
) -> tuple[list[GPXSegment], int, int]:
    """Parse one GPX file into cleaned segments.

    Returns ``(segments, dropped_short, dropped_empty)``, counted per raw
    ``<trkseg>`` (not per chunk). Any single track segment that fails to parse
    or clean is skipped rather than failing the whole file (a tired runner's
    collection always has a few bad recordings).
    """
    original_file = str(path.relative_to(gpx_dir)) if path.is_relative_to(gpx_dir) else path.name
    gpx = gpxpy.parse(_read_text(path))

    segments: list[GPXSegment] = []
    dropped_short = 0
    dropped_empty = 0

    for track_index, track in enumerate(gpx.tracks):
        for segment_index, trkseg in enumerate(track.segments):
            points = [
                (p.longitude, p.latitude, p.time.replace(tzinfo=None) if p.time else None)
                for p in trkseg.points
            ]
            if not points:
                dropped_empty += 1
                continue
            chunk_segments = _segments_from_points(
                points, path, original_file, track_index, segment_index, settings
            )
            if not chunk_segments:
                dropped_short += 1
                continue
            segments.extend(chunk_segments)

    return segments, dropped_short, dropped_empty


def segments_to_geodataframe(segments: list[GPXSegment]) -> gpd.GeoDataFrame:
    """Flatten segments into a GeoDataFrame (EPSG:4326) for geojson/parquet output."""
    rows = [
        {
            "segment_id": s.segment_id,
            "source_file": str(s.source_file),
            "original_file": s.original_file,
            "track_index": s.track_index,
            "segment_index": s.segment_index,
            "chunk_index": s.chunk_index,
            "length_m": s.length_m,
            "num_points": s.num_points,
            "start_time": s.start_time,
            "end_time": s.end_time,
            "geometry": s.geometry,
        }
        for s in segments
    ]
    return gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")


def _segment_in_city(segment: GPXSegment, city: BaseGeometry) -> bool:
    """True when the segment midpoint falls inside the city boundary."""
    mid = segment.geometry.interpolate(0.5, normalized=True)
    return bool(city.covers(mid))


def process(settings: Settings) -> tuple[list[GPXSegment], ProcessSummary]:
    """Discover, parse, and clean all GPX files under ``settings.gpx_dir``.

    When ``boundary_polygon`` exists, segments whose midpoint lies outside the
    city are dropped so Hanoi (or other) runs never become "missing" against
    an HCMC OSM clip.
    """
    files = discover_gpx_files(settings.gpx_dir)
    summary = ProcessSummary(files_seen=len(files))
    all_segments: list[GPXSegment] = []

    city: BaseGeometry | None = None
    if settings.boundary_polygon.is_file():
        city = load_osmconvert_poly(settings.boundary_polygon)

    for path in files:
        try:
            segments, dropped_short, dropped_empty = parse_gpx_file(
                path, settings.gpx_dir, settings
            )
        except Exception:
            summary.files_failed += 1
            continue
        if city is not None:
            kept: list[GPXSegment] = []
            for segment in segments:
                if _segment_in_city(segment, city):
                    kept.append(segment)
                else:
                    summary.segments_dropped_outside_city += 1
            segments = kept
        all_segments.extend(segments)
        summary.segments_dropped_short += dropped_short
        summary.segments_dropped_empty += dropped_empty

    summary.segments_kept = len(all_segments)
    summary.total_km = sum(s.length_m for s in all_segments) / 1000.0

    if all_segments:
        gdf = segments_to_geodataframe(all_segments)
        settings.output_dir.mkdir(parents=True, exist_ok=True)
        gdf.to_file(settings.output_dir / "segments.geojson", driver="GeoJSON")
        gdf.to_parquet(settings.output_dir / "segments.parquet")

    return all_segments, summary


def load_segments(output_dir: Path) -> list[GPXSegment]:
    """Reload segments previously written by :func:`process` (for later pipeline steps)."""
    gdf = gpd.read_parquet(output_dir / "segments.parquet")
    segments = []
    for row in gdf.itertuples():
        segments.append(
            GPXSegment(
                segment_id=row.segment_id,
                source_file=Path(row.source_file),
                original_file=row.original_file,
                track_index=row.track_index,
                segment_index=row.segment_index,
                chunk_index=row.chunk_index,
                geometry=row.geometry,
                length_m=row.length_m,
                num_points=row.num_points,
                start_time=None if pd.isna(row.start_time) else row.start_time,
                end_time=None if pd.isna(row.end_time) else row.end_time,
                bbox=geometry_bbox(row.geometry),
            )
        )
    return segments
