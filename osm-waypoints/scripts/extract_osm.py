#!/usr/bin/env python3
"""Create an OSM extract with a buffer around all GPX tracks."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from config import (
    BUFFER_KM,
    COUNTRY_OSM_FILE,
    GPX_DIR,
    OSM_EXTRACT,
    OSM_POLYGON,
)
from gpx_utils import compute_convex_polygon_with_buffer, load_track_points
from shapely.geometry import Polygon, mapping


def write_polygon_geojson(polygon: Polygon, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    feature = {
        "type": "Feature",
        "properties": {"buffer_km": BUFFER_KM},
        "geometry": mapping(polygon),
    }
    output_path.write_text(json.dumps(feature, indent=2) + "\n")


def extract_with_osmium(source_pbf: Path, polygon_file: Path, output_osm: Path) -> None:
    output_osm.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "osmium",
            "extract",
            "-p",
            str(polygon_file),
            "-o",
            str(output_osm),
            "-f",
            "osm",
            "--overwrite",
            str(source_pbf),
        ],
        check=True,
    )


def main() -> int:
    if not GPX_DIR.is_dir():
        print(f"GPX directory not found: {GPX_DIR}", file=sys.stderr)
        return 1

    if not COUNTRY_OSM_FILE.is_file():
        print(
            f"Country OSM file not found: {COUNTRY_OSM_FILE}\n"
            "Run `make country` first to download it.",
            file=sys.stderr,
        )
        return 1

    points = load_track_points(GPX_DIR)
    polygon = compute_convex_polygon_with_buffer(points, BUFFER_KM)
    min_lon, min_lat, max_lon, max_lat = polygon.bounds

    print(f"Loaded {len(points)} coordinates from {GPX_DIR}")
    print(f"Buffer: {BUFFER_KM * 1000:.0f} m")
    print(f"Convex hull vertices: {len(polygon.exterior.coords) - 1}")
    print(f"Polygon bounds: {min_lon:.6f},{min_lat:.6f},{max_lon:.6f},{max_lat:.6f}")

    write_polygon_geojson(polygon, OSM_POLYGON)
    extract_with_osmium(COUNTRY_OSM_FILE, OSM_POLYGON, OSM_EXTRACT)

    print(f"Wrote polygon to {OSM_POLYGON}")
    print(f"Wrote OSM extract to {OSM_EXTRACT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
