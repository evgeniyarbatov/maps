"""Per-cluster JOSM bundle: buffered .osm extract + GPX copies + cluster_meta.json."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
from pyproj import Transformer
from shapely.geometry import LineString

from gpx_osm_missing_paths.config import Settings
from gpx_osm_missing_paths.models import Cluster, GPXSegment
from gpx_osm_missing_paths.utils import atomic_write_json, geometry_bbox, utm_epsg_for


@dataclass
class ExtractSummary:
    """Rich-printable counters for ``gpx-osm extract``."""

    bundles_written: int = 0
    bundles_failed: int = 0


def _cluster_bbox_4326(cluster: Cluster, buffer_m: float) -> tuple[float, float, float, float]:
    """Bounding box of the representative line, buffered by ``buffer_m`` meters."""
    lon0, lat0 = cluster.representative_line.coords[0]
    epsg = utm_epsg_for(lon0, lat0)
    to_utm = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
    to_wgs84 = Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326", always_xy=True)

    line_utm_coords = [to_utm.transform(x, y) for x, y in cluster.representative_line.coords]
    buffered = LineString(line_utm_coords).buffer(buffer_m)
    minx, miny, maxx, maxy = buffered.bounds
    min_lon, min_lat = to_wgs84.transform(minx, miny)
    max_lon, max_lat = to_wgs84.transform(maxx, maxy)
    return (min_lon, min_lat, max_lon, max_lat)


def _write_osm_extract(pbf_path: str, bbox: tuple[float, float, float, float], out_path: str) -> None:
    bbox_str = ",".join(f"{v:.7f}" for v in bbox)
    subprocess.run(
        ["osmium", "extract", "--bbox", bbox_str, "--overwrite", "-o", out_path, pbf_path],
        check=True,
        capture_output=True,
        text=True,
    )


def _copy_gpx_files(cluster: Cluster, gpx_dir: Path, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    for original_file in cluster.source_files:
        src = gpx_dir / original_file
        if not src.is_file():
            continue
        dst = dest_dir / original_file
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def extract_clusters(
    settings: Settings, clusters: list[Cluster], segments: list[GPXSegment]
) -> ExtractSummary:
    """Write ``clusters/{slug}/`` bundles for every named, missing cluster."""
    summary = ExtractSummary()
    named_missing = [c for c in clusters if c.is_missing and c.slug]
    if not named_missing:
        return summary

    pbf_path = settings.resolve_osm_pbf()
    segments_by_id = {s.segment_id: s for s in segments}

    for cluster in named_missing:
        assert cluster.slug is not None
        slug_dir = settings.clusters_dir / cluster.slug
        try:
            slug_dir.mkdir(parents=True, exist_ok=True)

            bbox = _cluster_bbox_4326(cluster, settings.cluster_buffer_m)
            osm_out = slug_dir / f"{cluster.slug}.osm"
            _write_osm_extract(str(pbf_path), bbox, str(osm_out))

            _copy_gpx_files(cluster, settings.gpx_dir, slug_dir / "gpx")

            rep_gdf = gpd.GeoDataFrame(
                {"cluster_id": [cluster.cluster_id], "human_name": [cluster.human_name]},
                geometry=[cluster.representative_line],
                crs="EPSG:4326",
            )
            rep_gdf.to_file(slug_dir / "representative.geojson", driver="GeoJSON")

            member_segments = [
                segments_by_id[sid] for sid in cluster.segment_ids if sid in segments_by_id
            ]
            if member_segments:
                all_gdf = gpd.GeoDataFrame(
                    {
                        "segment_id": [s.segment_id for s in member_segments],
                        "original_file": [s.original_file for s in member_segments],
                        "length_m": [s.length_m for s in member_segments],
                    },
                    geometry=[s.geometry for s in member_segments],
                    crs="EPSG:4326",
                )
                all_gdf.to_file(slug_dir / "all_segments.geojson", driver="GeoJSON")

            meta = cluster.to_meta_dict(
                bbox=geometry_bbox(cluster.representative_line),
                boundary_polygon=str(settings.boundary_polygon),
                city_slug=settings.city_slug,
                osm_pbf=str(pbf_path),
                josm_notes=(
                    f"Open {cluster.slug}.osm in JOSM, then load the files in gpx/ as GPX "
                    "reference layers. Draw the missing path where the traces agree."
                ),
            )
            atomic_write_json(slug_dir / "cluster_meta.json", meta)

            summary.bundles_written += 1
        except (subprocess.CalledProcessError, OSError):
            summary.bundles_failed += 1

    return summary
