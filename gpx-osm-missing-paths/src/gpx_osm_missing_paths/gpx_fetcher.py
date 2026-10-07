"""Fetches raw GPX tracks from the evgeniyarbatov/gpx-data GeoParquet export into GPX_DIR."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

import geopandas as gpd
from pyproj import Transformer
from shapely.geometry import LineString, Point

from gpx_osm_missing_paths.config import Settings
from gpx_osm_missing_paths.utils import slugify, utm_epsg_for


@dataclass
class FetchGpxSummary:
    """Rich-printable counters for ``gpx-osm fetch-gpx``."""

    tracks_seen: int = 0
    tracks_kept: int = 0
    tracks_skipped_no_geometry: int = 0
    files_written: int = 0


def checkout_gpx_data_repo(settings: Settings) -> Path:
    """Clone ``gpx_data_repo_url`` if missing, else fast-forward pull. Returns its local path."""
    repo_dir = settings.gpx_data_repo_dir
    if (repo_dir / ".git").is_dir():
        subprocess.run(["git", "-C", str(repo_dir), "pull", "--ff-only"], check=True)
    else:
        repo_dir.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", settings.gpx_data_repo_url, str(repo_dir)], check=True)
    return repo_dir


def _within_radius(line: LineString, lat: float, lon: float, radius_km: float) -> bool:
    """True when any point of ``line`` (WGS84) is within ``radius_km`` of (lat, lon)."""
    epsg = utm_epsg_for(lon, lat)
    to_utm = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
    point_utm = Point(to_utm.transform(lon, lat))
    line_utm = LineString([to_utm.transform(x, y) for x, y in line.coords])
    return bool(point_utm.distance(line_utm) <= radius_km * 1000.0)


def _write_gpx(path: Path, name: str, line: LineString) -> None:
    """Write a minimal single-track GPX 1.1 file.

    gpx-data's parquet tracks are already-simplified LineStrings with no per-point
    elevation or timestamp, so this writes coordinates only — gpx_processor.py (the
    only other place that touches GPX I/O) tolerates missing time/elevation already.
    """
    points = "\n".join(
        f'      <trkpt lat="{lat}" lon="{lon}"></trkpt>' for lon, lat in line.coords
    )
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<gpx version="1.1" creator="gpx-osm-missing-paths" '
        'xmlns="http://www.topografix.com/GPX/1/1">\n'
        "  <trk>\n"
        f"    <name>{escape(name)}</name>\n"
        "    <trkseg>\n"
        f"{points}\n"
        "    </trkseg>\n"
        "  </trk>\n"
        "</gpx>\n",
        encoding="utf-8",
    )


def fetch_gpx_from_dir(
    settings: Settings,
    repo_dir: Path,
    lat: float | None,
    lon: float | None,
    radius_km: float | None,
) -> FetchGpxSummary:
    """Convert every track in ``repo_dir/data/parquet/**/*.parquet`` into a ``.gpx`` file.

    When ``lat``/``lon``/``radius_km`` are all given, only tracks passing within
    ``radius_km`` of the point are written — ``gpx-data`` spans many cities/countries
    and most of it is irrelevant to any one mapping session.
    """
    parquet_files = sorted((repo_dir / "data" / "parquet").rglob("*.parquet"))
    summary = FetchGpxSummary()
    settings.gpx_dir.mkdir(parents=True, exist_ok=True)
    apply_filter = lat is not None and lon is not None and radius_km is not None

    for parquet_path in parquet_files:
        source = parquet_path.parent.name
        gdf = gpd.read_parquet(parquet_path)
        for idx, row in enumerate(gdf.itertuples(index=False)):
            summary.tracks_seen += 1
            line = row.geometry
            if line is None or line.is_empty:
                summary.tracks_skipped_no_geometry += 1
                continue
            if apply_filter and not _within_radius(line, lat, lon, radius_km):  # type: ignore[arg-type]
                continue

            summary.tracks_kept += 1
            track_name = str(getattr(row, "name", "") or f"{source}_{idx}")
            out_name = (
                f"{source}__{slugify(parquet_path.stem)}__{slugify(track_name)}__{idx}.gpx"
            )
            _write_gpx(settings.gpx_dir / out_name, track_name, line)
            summary.files_written += 1

    return summary


def fetch_gpx(
    settings: Settings,
    lat: float | None = None,
    lon: float | None = None,
    radius_km: float | None = None,
) -> FetchGpxSummary:
    """Checkout/update ``gpx-data`` and convert its parquet tracks into ``GPX_DIR``."""
    repo_dir = checkout_gpx_data_repo(settings)
    return fetch_gpx_from_dir(settings, repo_dir, lat, lon, radius_km)
