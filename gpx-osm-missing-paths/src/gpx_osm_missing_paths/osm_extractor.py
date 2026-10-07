"""Per-cluster JOSM bundle: buffered .osm extract + GPX copies + cluster_meta.json."""

from __future__ import annotations

import shutil
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
from pyproj import Transformer
from shapely.geometry import LineString

from gpx_osm_missing_paths.config import Settings
from gpx_osm_missing_paths.models import Cluster, GPXSegment
from gpx_osm_missing_paths.utils import atomic_write_json, utm_epsg_for


@dataclass
class ExtractSummary:
    """Rich-printable counters for ``gpx-osm extract``."""

    bundles_written: int = 0
    bundles_failed: int = 0


def _cluster_bbox_4326(cluster: Cluster, buffer_m: float) -> tuple[float, float, float, float]:
    """Bounding box of the representative line, buffered by ``buffer_m`` meters.

    Returns ``(min_lon, min_lat, max_lon, max_lat)`` for ``osmium extract --bbox``.
    """
    lon0, lat0 = cluster.representative_line.coords[0]
    epsg = utm_epsg_for(lon0, lat0)
    to_utm = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
    to_wgs84 = Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326", always_xy=True)

    line_utm_coords = [to_utm.transform(x, y) for x, y in cluster.representative_line.coords]
    buffered = LineString(line_utm_coords).buffer(buffer_m)
    minx, miny, maxx, maxy = buffered.bounds
    # Transform all four corners; UTM→WGS84 is not axis-aligned, so min/max of
    # the transformed corners is the safe envelope for osmium.
    corners = [
        to_wgs84.transform(minx, miny),
        to_wgs84.transform(minx, maxy),
        to_wgs84.transform(maxx, miny),
        to_wgs84.transform(maxx, maxy),
    ]
    lons = [c[0] for c in corners]
    lats = [c[1] for c in corners]
    return (min(lons), min(lats), max(lons), max(lats))


def _strip_incomplete_relations(osm_path: Path) -> int:
    """Remove relations with missing members so JOSM does not show broken multipolygons.

    ``osmium extract`` keeps parent relations (often country/province boundaries) even
    when most members lie outside the bbox. JOSM draws those as huge incomplete red
    outlines that look like a corrupted extract.
    """
    tree = ET.parse(osm_path)
    root = tree.getroot()
    node_ids = {el.get("id") for el in root.findall("node")}
    way_ids = {el.get("id") for el in root.findall("way")}
    rel_ids = {el.get("id") for el in root.findall("relation")}

    removed = 0
    # Iterate until stable: dropping a relation can complete another that only
    # referenced it as a missing member (rare, but cheap for small extracts).
    changed = True
    while changed:
        changed = False
        for rel in list(root.findall("relation")):
            incomplete = False
            for mem in rel.findall("member"):
                mtype, ref = mem.get("type"), mem.get("ref")
                if (
                    (mtype == "node" and ref not in node_ids)
                    or (mtype == "way" and ref not in way_ids)
                    or (mtype == "relation" and ref not in rel_ids)
                ):
                    incomplete = True
                    break
            if incomplete:
                root.remove(rel)
                rel_ids.discard(rel.get("id"))
                removed += 1
                changed = True

    tree.write(osm_path, encoding="UTF-8", xml_declaration=True)
    return removed


def _osm_object_counts(osm_path: Path) -> tuple[int, int, int]:
    """Return ``(nodes, ways, relations)`` by scanning the XML (no full DOM)."""
    nodes = ways = relations = 0
    for _event, elem in ET.iterparse(osm_path, events=("end",)):
        if elem.tag == "node":
            nodes += 1
        elif elem.tag == "way":
            ways += 1
        elif elem.tag == "relation":
            relations += 1
        elem.clear()
    return nodes, ways, relations


def _write_osm_extract(
    pbf_path: Path, bbox: tuple[float, float, float, float], out_path: Path
) -> None:
    """Extract a JOSM-ready ``.osm`` clip: complete ways, header bounds, no broken relations."""
    min_lon, min_lat, max_lon, max_lat = bbox
    if min_lon >= max_lon or min_lat >= max_lat:
        raise ValueError(f"Invalid extract bbox: {bbox}")

    bbox_str = f"{min_lon:.7f},{min_lat:.7f},{max_lon:.7f},{max_lat:.7f}"
    subprocess.run(
        [
            "osmium",
            "extract",
            "--bbox",
            bbox_str,
            "--strategy",
            "complete_ways",
            "--set-bounds",
            "--overwrite",
            "-o",
            str(out_path),
            str(pbf_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    nodes, ways, _rels = _osm_object_counts(out_path)
    if nodes == 0 and ways == 0:
        out_path.unlink(missing_ok=True)
        raise RuntimeError(
            f"Empty OSM extract for bbox {bbox_str} from {pbf_path.name} "
            "(cluster geometry is outside the city PBF coverage)"
        )

    _strip_incomplete_relations(out_path)


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
            if slug_dir.exists():
                shutil.rmtree(slug_dir)
            slug_dir.mkdir(parents=True, exist_ok=True)

            bbox = _cluster_bbox_4326(cluster, settings.cluster_buffer_m)
            osm_out = slug_dir / f"{cluster.slug}.osm"
            _write_osm_extract(pbf_path, bbox, osm_out)

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
                bbox=list(bbox),
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
        except (subprocess.CalledProcessError, OSError, RuntimeError, ValueError):
            summary.bundles_failed += 1
            if slug_dir.exists():
                shutil.rmtree(slug_dir, ignore_errors=True)

    return summary
