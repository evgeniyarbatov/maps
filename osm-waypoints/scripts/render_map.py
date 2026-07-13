#!/usr/bin/env python3
"""Render validated waypoints on a high-resolution contextily basemap."""

from __future__ import annotations

import json
import sys

import contextily as cx
import geopandas as gpd
import matplotlib.pyplot as plt
from config import DATA_DIR, MAP_DPI, MAP_IMAGE, MAP_WIDTH_IN, POIS_RAW, POIS_VALIDATED
from shapely.geometry import Point


def load_waypoints() -> list[dict]:
    source = POIS_VALIDATED if POIS_VALIDATED.is_file() else POIS_RAW
    if not source.is_file():
        raise FileNotFoundError(
            f"No waypoint data found. Expected {POIS_VALIDATED} or {POIS_RAW}."
        )

    payload = json.loads(source.read_text())
    waypoints = payload.get("waypoints", [])

    if source == POIS_VALIDATED:
        return [w for w in waypoints if w.get("valid", True)]

    return waypoints


def main() -> int:
    try:
        waypoints = load_waypoints()
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 1

    if not waypoints:
        print("No waypoints to render.")
        return 0

    geometry = [Point(w["lon"], w["lat"]) for w in waypoints]
    gdf = gpd.GeoDataFrame(waypoints, geometry=geometry, crs="EPSG:4326")
    gdf = gdf.to_crs(epsg=3857)

    minx, miny, maxx, maxy = gdf.total_bounds
    pad_x = max((maxx - minx) * 0.15, 500)
    pad_y = max((maxy - miny) * 0.15, 500)

    aspect = max((maxy - miny + 2 * pad_y) / (maxx - minx + 2 * pad_x), 0.5)
    width = MAP_WIDTH_IN
    height = width * aspect

    fig, ax = plt.subplots(figsize=(width, height), dpi=MAP_DPI)
    gdf.plot(
        ax=ax,
        color="#d62728",
        edgecolor="white",
        linewidth=0.6,
        markersize=70,
        alpha=0.9,
        zorder=3,
    )

    for _, row in gdf.iterrows():
        ax.annotate(
            row["name"],
            xy=(row.geometry.x, row.geometry.y),
            xytext=(4, 4),
            textcoords="offset points",
            fontsize=7,
            color="#1f1f1f",
            bbox={"boxstyle": "round,pad=0.2", "fc": "white", "ec": "none", "alpha": 0.75},
            zorder=4,
        )

    ax.set_xlim(minx - pad_x, maxx + pad_x)
    ax.set_ylim(miny - pad_y, maxy + pad_y)
    ax.set_axis_off()

    cx.add_basemap(ax, source=cx.providers.OpenStreetMap.Mapnik, zoom="auto")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(MAP_IMAGE, bbox_inches="tight", pad_inches=0.1, facecolor="white")
    plt.close(fig)

    print(f"Rendered {len(waypoints)} waypoints to {MAP_IMAGE} ({MAP_DPI} DPI)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
