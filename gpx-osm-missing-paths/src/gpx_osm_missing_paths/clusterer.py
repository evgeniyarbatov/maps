"""Group GPX segments that trace the same physical path.

Heuristic (documented in ``docs/architecture.md``): rough spatial bucketing via
``geopandas.sjoin`` on buffered geometries, then within-bucket pairwise checks
(Hausdorff distance + buffered overlap fraction + bearing similarity), then
connected components over the resulting proximity graph. Intentionally errs on
the side of over-clustering — a user can split a cluster in JOSM far more
easily than they can find 15 near-duplicate traces scattered across separate
directories.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import geopandas as gpd
import networkx as nx
import pandas as pd
from pyproj import Transformer
from shapely.geometry import LineString

from gpx_osm_missing_paths.config import Settings
from gpx_osm_missing_paths.models import Cluster, GPXSegment, save_clusters_state
from gpx_osm_missing_paths.utils import bearing_diff_deg, line_bearing_deg, utm_epsg_for

# Candidate-pair prefilter: only segments whose buffers touch are checked further.
SJOIN_BUFFER_M = 30.0
# Buffer used when measuring what fraction of the shorter segment overlaps the longer one.
OVERLAP_BUFFER_M = 10.0
# Two segments connect if they are this close (Hausdorff, in meters)...
HAUSDORFF_THRESHOLD_M = 25.0
# ...and this much of the shorter segment's length falls inside the other's overlap buffer.
OVERLAP_FRACTION_THRESHOLD = 0.40
# ...or, alternatively, they are near-collinear (bearing diff, treating reverse direction
# as identical) below this many degrees while still meeting the overlap fraction.
BEARING_THRESHOLD_DEG = 30.0


@dataclass
class ClusterSummary:
    """Rich-printable counters for ``gpx-osm cluster``."""

    segments_in: int = 0
    clusters_out: int = 0
    largest_cluster_size: int = 0
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


def _overlap_fraction(a: LineString, b: LineString) -> float:
    """Fraction of the shorter line's length that falls within a buffer of the other."""
    len_a, len_b = a.length, b.length
    if len_a == 0 or len_b == 0:
        return 0.0
    if len_a <= len_b:
        shorter, longer, shorter_len = a, b, len_a
    else:
        shorter, longer, shorter_len = b, a, len_b
    overlap_len = shorter.intersection(longer.buffer(OVERLAP_BUFFER_M)).length
    return float(overlap_len / shorter_len)


def _should_connect(a: LineString, b: LineString) -> bool:
    overlap_frac = _overlap_fraction(a, b)
    if overlap_frac <= OVERLAP_FRACTION_THRESHOLD:
        return False
    hausdorff_m = a.hausdorff_distance(b)
    if hausdorff_m < HAUSDORFF_THRESHOLD_M:
        return True
    bearing_diff = bearing_diff_deg(line_bearing_deg(a), line_bearing_deg(b))
    return bearing_diff <= BEARING_THRESHOLD_DEG


def _candidate_pairs(projected: dict[str, LineString]) -> list[tuple[str, str]]:
    """Prefilter pairs via a spatial join on buffered geometries (avoids O(n^2))."""
    ids = list(projected.keys())
    gdf = gpd.GeoDataFrame(
        {"segment_id": ids},
        geometry=[projected[i].buffer(SJOIN_BUFFER_M) for i in ids],
    )
    joined = gpd.sjoin(gdf, gdf, how="inner", predicate="intersects")
    pairs = set()
    for left, right in zip(joined["segment_id_left"], joined["segment_id_right"], strict=True):
        if left < right:
            pairs.add((left, right))
        elif right < left:
            pairs.add((right, left))
    return sorted(pairs)


def cluster_segments(segments: list[GPXSegment]) -> tuple[dict[str, str], ClusterSummary]:
    """Assign each segment a ``cluster_id``. Returns the mapping and summary counters."""
    summary = ClusterSummary(segments_in=len(segments))
    if not segments:
        return {}, summary

    projected, _epsg = _project_all(segments)

    graph = nx.Graph()
    graph.add_nodes_from(projected.keys())
    for left, right in _candidate_pairs(projected):
        if _should_connect(projected[left], projected[right]):
            graph.add_edge(left, right)

    components = sorted(
        (sorted(component) for component in nx.connected_components(graph)),
        key=lambda component: component[0],
    )

    segment_to_cluster: dict[str, str] = {}
    for index, component in enumerate(components):
        cluster_id = f"cluster_{index:04d}"
        for segment_id in component:
            segment_to_cluster[segment_id] = cluster_id
        summary.largest_cluster_size = max(summary.largest_cluster_size, len(component))
        if len(component) == 1:
            summary.singleton_clusters += 1

    summary.clusters_out = len(components)
    return segment_to_cluster, summary


def build_clusters(
    segments: list[GPXSegment], segment_to_cluster: dict[str, str]
) -> list[Cluster]:
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
        clusters.append(
            Cluster(
                cluster_id=cluster_id,
                segment_ids=[m.segment_id for m in members],
                representative_line=representative.geometry,
                num_gpx_traces=len(members),
                avg_length_m=sum(lengths) / len(lengths),
                min_length_m=min(lengths),
                max_length_m=max(lengths),
                total_length_m=sum(lengths),
                representative_length_m=representative.length_m,
                bbox=(bounds[0], bounds[1], bounds[2], bounds[3]),
                source_files=sorted({m.original_file for m in members}),
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
    segment_to_cluster, summary = cluster_segments(segments)
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
