"""Coverage vs existing OSM ways — the product gate for which clusters get JOSM bundles."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import osmium
import shapely.wkb
from pyproj import Transformer
from shapely.geometry import LineString
from shapely.ops import unary_union

from gpx_osm_missing_paths.clusterer import clusters_to_geodataframe
from gpx_osm_missing_paths.config import Settings
from gpx_osm_missing_paths.models import Cluster, save_clusters_state
from gpx_osm_missing_paths.utils import utm_epsg_for

# Highways treated as "a path already exists here": dedicated path infra plus the
# unclassified/residential/track tags Vietnamese alleys are commonly (mis)tagged with.
PATH_HIGHWAY_VALUES = {
    "footway",
    "path",
    "steps",
    "pedestrian",
    "cycleway",
    "bridleway",
    "residential",
    "service",
    "living_street",
    "track",
    "unclassified",
}

OSM_PATHS_CACHE_NAME = "osm_paths.parquet"


class _PathWayHandler(osmium.SimpleHandler):
    """Collects path-like ways as WGS84 LineStrings with their highway tag."""

    def __init__(self) -> None:
        super().__init__()
        self._wkbfab = osmium.geom.WKBFactory()
        self.rows: list[dict[str, object]] = []

    def way(self, w: osmium.osm.Way) -> None:
        highway = w.tags.get("highway")
        if highway not in PATH_HIGHWAY_VALUES:
            return
        try:
            wkb = self._wkbfab.create_linestring(w)
        except (RuntimeError, osmium.InvalidLocationError):
            return
        self.rows.append(
            {
                "osm_id": w.id,
                "highway": highway,
                "name": w.tags.get("name", ""),
                "geometry": shapely.wkb.loads(wkb, hex=True),
            }
        )


def _extract_path_ways(pbf_path: Path) -> gpd.GeoDataFrame:
    handler = _PathWayHandler()
    handler.apply_file(str(pbf_path), locations=True)
    if not handler.rows:
        return gpd.GeoDataFrame(
            {"osm_id": [], "highway": [], "name": []}, geometry=[], crs="EPSG:4326"
        )
    return gpd.GeoDataFrame(handler.rows, geometry="geometry", crs="EPSG:4326")


def load_osm_paths(pbf_path: Path, output_dir: Path) -> gpd.GeoDataFrame:
    """Path-like ways from the city PBF, cached in ``output/`` until the PBF changes."""
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_path = output_dir / OSM_PATHS_CACHE_NAME
    if cache_path.is_file() and cache_path.stat().st_mtime >= pbf_path.stat().st_mtime:
        return gpd.read_parquet(cache_path)

    gdf = _extract_path_ways(pbf_path)
    gdf.to_parquet(cache_path)
    return gdf


@dataclass
class MissingFilterSummary:
    """Rich-printable counters for ``gpx-osm filter-missing``."""

    clusters_in: int = 0
    missing_kept: int = 0
    covered_skipped: int = 0
    few_traces_skipped: int = 0


def _project_paths(paths: gpd.GeoDataFrame, epsg: int) -> gpd.GeoDataFrame:
    if paths.empty:
        return paths
    return paths.to_crs(epsg=epsg)


def _coverage_fraction(line_utm: LineString, paths_utm: gpd.GeoDataFrame, buffer_m: float) -> float:
    if line_utm.length == 0:
        return 0.0
    if paths_utm.empty:
        return 0.0
    minx, miny, maxx, maxy = line_utm.bounds
    nearby_idx = list(
        paths_utm.sindex.intersection(
            (minx - buffer_m, miny - buffer_m, maxx + buffer_m, maxy + buffer_m)
        )
    )
    if not nearby_idx:
        return 0.0
    nearby = paths_utm.iloc[nearby_idx]
    corridor = unary_union([geom.buffer(buffer_m) for geom in nearby.geometry])
    return float(line_utm.intersection(corridor).length / line_utm.length)


def filter_missing(
    settings: Settings, clusters: list[Cluster]
) -> tuple[list[Cluster], MissingFilterSummary]:
    """Set ``osm_coverage_fraction`` / ``is_missing`` on every cluster; write missing-only geojson."""
    summary = MissingFilterSummary(clusters_in=len(clusters))
    if not clusters:
        return clusters, summary

    pbf_path = settings.resolve_osm_pbf()
    paths = load_osm_paths(pbf_path, settings.output_dir)

    lon0, lat0 = clusters[0].representative_line.coords[0]
    epsg = utm_epsg_for(lon0, lat0)
    to_utm = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
    paths_utm = _project_paths(paths, epsg)

    for c in clusters:
        line_utm = LineString([to_utm.transform(x, y) for x, y in c.representative_line.coords])
        coverage = _coverage_fraction(line_utm, paths_utm, settings.existing_path_match_buffer_m)
        c.osm_coverage_fraction = coverage
        poorly_covered = coverage < settings.missing_coverage_threshold
        if poorly_covered and c.num_gpx_traces < settings.min_cluster_traces:
            c.is_missing = False
            summary.few_traces_skipped += 1
        elif poorly_covered:
            c.is_missing = True
            summary.missing_kept += 1
        else:
            c.is_missing = False
            summary.covered_skipped += 1

    missing = [c for c in clusters if c.is_missing]
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    if missing:
        gdf = clusters_to_geodataframe(missing)
        gdf["osm_coverage_fraction"] = [c.osm_coverage_fraction for c in missing]
        gdf["is_missing"] = True
        gdf.to_file(settings.output_dir / "clusters_missing.geojson", driver="GeoJSON")

    save_clusters_state(settings.output_dir / "clusters_state.json", clusters)
    return clusters, summary
