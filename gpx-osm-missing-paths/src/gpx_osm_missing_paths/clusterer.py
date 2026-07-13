"""Group GPX segments that trace the same physical path.

Heuristic (documented in ``docs/architecture.md``):

1. Project segments to a shared local UTM (meters).
2. Prefilter candidate pairs by midpoint proximity (spatial join).
3. Two segments match when they cover the same stretch of ground:
   midpoints close, high buffered overlap of the shorter line, and low
   mean point-to-line distance (tolerant of urban GPS noise, not of
   merely parallel nearby streets).
4. Seed-based greedy assignment (longest segment first as representative)
   so matches do not chain transitively along a whole running network into
   one city-spanning mega-cluster.

``num_gpx_traces`` counts unique source GPX files, not chunked segments.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

import geopandas as gpd
import pandas as pd
from pyproj import Transformer
from shapely.geometry import LineString

from gpx_osm_missing_paths.config import Settings
from gpx_osm_missing_paths.models import Cluster, GPXSegment, save_clusters_state
from gpx_osm_missing_paths.utils import utm_epsg_for

# Sample count for mean point-to-line distance (endpoints + interior).
_MEAN_DIST_SAMPLES = 11


@dataclass
class ClusterSummary:
    """Rich-printable counters for ``gpx-osm cluster``."""

    segments_in: int = 0
    clusters_out: int = 0
    multi_trace_clusters: int = 0
    largest_cluster_segments: int = 0
    largest_cluster_traces: int = 0
    singleton_clusters: int = 0


def _project_all(segments: list[GPXSegment]) -> tuple[dict[str, LineString], int]:
    """Project every segment geometry into one shared local UTM CRS (meters)."""
    lons = [s.geometry.centroid.x for s in segments]
    lats = [s.geometry.centroid.y for s in segments]
    epsg = utm_epsg_for(sum(lons) / len(lons), sum(lats) / len(lats))
    to_utm = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
    projected = {
        s.segment_id: LineString([to_utm.transform(x, y) for x, y in s.geometry.coords])
        for s in segments
    }
    return projected, epsg


def _mean_distance_m(a: LineString, b: LineString, samples: int = _MEAN_DIST_SAMPLES) -> float:
    """Symmetric mean point-to-line distance (max of the two directions)."""
    if a.is_empty or b.is_empty:
        return float("inf")
    n = max(samples, 2)

    def _directed(src: LineString, dst: LineString) -> float:
        total = 0.0
        for i in range(n):
            t = i / (n - 1)
            total += src.interpolate(t, normalized=True).distance(dst)
        return total / n

    return max(_directed(a, b), _directed(b, a))


def _overlap_fraction(a: LineString, b: LineString, buffer_m: float) -> float:
    """Fraction of the shorter line's length that falls within a buffer of the other."""
    len_a, len_b = a.length, b.length
    if len_a == 0 or len_b == 0:
        return 0.0
    if len_a <= len_b:
        shorter, longer, shorter_len = a, b, len_a
    else:
        shorter, longer, shorter_len = b, a, len_b
    overlap_len = shorter.intersection(longer.buffer(buffer_m)).length
    return float(overlap_len / shorter_len)


def _should_match(
    a: LineString,
    b: LineString,
    *,
    overlap_buffer_m: float,
    overlap_fraction: float,
    mean_distance_m: float,
    midpoint_max_m: float,
) -> bool:
    """True when a and b cover the same physical stretch (not merely nearby)."""
    mid_a = a.interpolate(0.5, normalized=True)
    mid_b = b.interpolate(0.5, normalized=True)
    if mid_a.distance(mid_b) > midpoint_max_m:
        return False
    if _overlap_fraction(a, b, overlap_buffer_m) < overlap_fraction:
        return False
    return _mean_distance_m(a, b) <= mean_distance_m


def _midpoint_candidates(
    projected: dict[str, LineString], midpoint_max_m: float
) -> dict[str, set[str]]:
    """For each segment id, other ids whose midpoints fall within ``midpoint_max_m``."""
    ids = list(projected.keys())
    midpoints = {sid: projected[sid].interpolate(0.5, normalized=True) for sid in ids}
    gdf = gpd.GeoDataFrame(
        {"segment_id": ids},
        geometry=[midpoints[sid].buffer(midpoint_max_m) for sid in ids],
    )
    joined = gpd.sjoin(gdf, gdf, how="inner", predicate="intersects")
    candidates: dict[str, set[str]] = defaultdict(set)
    for left, right in zip(joined["segment_id_left"], joined["segment_id_right"], strict=True):
        if left != right:
            candidates[left].add(right)
    return candidates


def cluster_segments(
    segments: list[GPXSegment], settings: Settings
) -> tuple[dict[str, str], ClusterSummary]:
    """Assign each segment a ``cluster_id``. Returns the mapping and summary counters."""
    summary = ClusterSummary(segments_in=len(segments))
    if not segments:
        return {}, summary

    projected, _epsg = _project_all(segments)
    candidates = _midpoint_candidates(projected, settings.cluster_midpoint_max_m)

    # Longest first: better seed geometry for a physical stretch.
    order = sorted(
        projected.keys(),
        key=lambda sid: projected[sid].length,
        reverse=True,
    )
    remaining = set(projected.keys())
    components: list[list[str]] = []

    for seed in order:
        if seed not in remaining:
            continue
        members = [seed]
        remaining.remove(seed)
        seed_geom = projected[seed]
        for other in sorted(candidates[seed] & remaining):
            if _should_match(
                seed_geom,
                projected[other],
                overlap_buffer_m=settings.cluster_overlap_buffer_m,
                overlap_fraction=settings.cluster_overlap_fraction,
                mean_distance_m=settings.cluster_mean_distance_m,
                midpoint_max_m=settings.cluster_midpoint_max_m,
            ):
                members.append(other)
                remaining.remove(other)
        components.append(sorted(members))

    components.sort(key=lambda component: component[0])

    segment_to_cluster: dict[str, str] = {}
    id_to_file = {s.segment_id: s.original_file for s in segments}
    for index, component in enumerate(components):
        cluster_id = f"cluster_{index:04d}"
        for segment_id in component:
            segment_to_cluster[segment_id] = cluster_id
        n_seg = len(component)
        n_traces = len({id_to_file[sid] for sid in component})
        summary.largest_cluster_segments = max(summary.largest_cluster_segments, n_seg)
        summary.largest_cluster_traces = max(summary.largest_cluster_traces, n_traces)
        if n_traces == 1:
            summary.singleton_clusters += 1
        else:
            summary.multi_trace_clusters += 1

    summary.clusters_out = len(components)
    return segment_to_cluster, summary


def build_clusters(segments: list[GPXSegment], segment_to_cluster: dict[str, str]) -> list[Cluster]:
    """Aggregate segments per ``cluster_id`` into ``Cluster`` objects."""
    by_cluster: dict[str, list[GPXSegment]] = {}
    for segment in segments:
        cluster_id = segment_to_cluster[segment.segment_id]
        by_cluster.setdefault(cluster_id, []).append(segment)

    clusters: list[Cluster] = []
    for cluster_id, members in sorted(by_cluster.items()):
        lengths = [m.length_m for m in members]
        representative = max(members, key=lambda m: m.length_m)
        bounds = gpd.GeoSeries([m.geometry for m in members]).total_bounds
        source_files = sorted({m.original_file for m in members})
        clusters.append(
            Cluster(
                cluster_id=cluster_id,
                segment_ids=[m.segment_id for m in members],
                representative_line=representative.geometry,
                num_gpx_traces=len(source_files),
                avg_length_m=sum(lengths) / len(lengths),
                min_length_m=min(lengths),
                max_length_m=max(lengths),
                total_length_m=sum(lengths),
                representative_length_m=representative.length_m,
                bbox=(bounds[0], bounds[1], bounds[2], bounds[3]),
                source_files=source_files,
                created_at=datetime.now(),
            )
        )
    return clusters


def clusters_to_geodataframe(clusters: list[Cluster]) -> gpd.GeoDataFrame:
    """Flatten clusters (representative geometry only) for geojson/parquet output."""
    rows = [
        {
            "cluster_id": c.cluster_id,
            "num_gpx_traces": c.num_gpx_traces,
            "avg_length_m": c.avg_length_m,
            "total_length_m": c.total_length_m,
            "representative_length_m": c.representative_length_m,
            "source_files": ",".join(c.source_files),
            "geometry": c.representative_line,
        }
        for c in clusters
    ]
    return gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")


def cluster(settings: Settings, segments: list[GPXSegment]) -> tuple[list[Cluster], ClusterSummary]:
    """Cluster segments and write ``output/clusters_raw.geojson`` + assignment table."""
    segment_to_cluster, summary = cluster_segments(segments, settings)
    clusters = build_clusters(segments, segment_to_cluster)

    settings.output_dir.mkdir(parents=True, exist_ok=True)
    if clusters:
        clusters_to_geodataframe(clusters).to_file(
            settings.output_dir / "clusters_raw.geojson", driver="GeoJSON"
        )
    mapping = pd.DataFrame(
        {"segment_id": list(segment_to_cluster), "cluster_id": list(segment_to_cluster.values())}
    )
    mapping.to_parquet(settings.output_dir / "segment_cluster_map.parquet")
    save_clusters_state(settings.output_dir / "clusters_state.json", clusters)

    return clusters, summary
