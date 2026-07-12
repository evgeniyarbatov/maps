"""Clustering: same-stretch merge, no network chaining, unique GPX counts."""

from pathlib import Path

from shapely.geometry import LineString

from gpx_osm_missing_paths.clusterer import build_clusters, cluster_segments
from gpx_osm_missing_paths.config import Settings
from gpx_osm_missing_paths.models import GPXSegment
from gpx_osm_missing_paths.utils import geometry_bbox, line_length_m


def _seg(
    sid: str,
    coords: list[tuple[float, float]],
    original_file: str,
) -> GPXSegment:
    line = LineString(coords)
    return GPXSegment(
        segment_id=sid,
        source_file=Path(original_file),
        original_file=original_file,
        track_index=0,
        segment_index=0,
        chunk_index=0,
        geometry=line,
        length_m=line_length_m(line),
        num_points=len(coords),
        start_time=None,
        end_time=None,
        bbox=geometry_bbox(line),
    )


def test_parallel_offset_traces_merge() -> None:
    """Two GPS-noisy traces of the same alley become one multi-file cluster."""
    # ~100m N-S alley near HCMC (~10.8N, 106.7E); second line offset ~8m east
    a = [
        (106.70000, 10.80000),
        (106.70000, 10.80090),
    ]
    b = [
        (106.70007, 10.80000),
        (106.70007, 10.80090),
    ]
    segments = [
        _seg("a#c0", a, "run_a.gpx"),
        _seg("b#c0", b, "run_b.gpx"),
    ]
    settings = Settings()
    mapping, summary = cluster_segments(segments, settings)
    assert mapping["a#c0"] == mapping["b#c0"]
    assert summary.multi_trace_clusters == 1
    assert summary.singleton_clusters == 0

    clusters = build_clusters(segments, mapping)
    assert len(clusters) == 1
    assert clusters[0].num_gpx_traces == 2
    assert set(clusters[0].source_files) == {"run_a.gpx", "run_b.gpx"}


def test_distant_paths_stay_separate() -> None:
    """Unrelated paths several km apart do not merge."""
    near = [(106.70000, 10.80000), (106.70000, 10.80090)]
    far = [(106.75000, 10.85000), (106.75000, 10.85090)]
    segments = [
        _seg("n#c0", near, "near.gpx"),
        _seg("f#c0", far, "far.gpx"),
    ]
    mapping, summary = cluster_segments(segments, Settings())
    assert mapping["n#c0"] != mapping["f#c0"]
    assert summary.singleton_clusters == 2
    assert summary.multi_trace_clusters == 0


def test_num_gpx_traces_counts_files_not_chunks() -> None:
    """Two chunks from the same file still count as one trace."""
    line = [(106.70000, 10.80000), (106.70000, 10.80090)]
    segments = [
        _seg("same#c0", line, "only.gpx"),
        _seg("same#c1", line, "only.gpx"),
    ]
    mapping, _ = cluster_segments(segments, Settings())
    clusters = build_clusters(segments, mapping)
    assert len(clusters) == 1
    assert clusters[0].num_gpx_traces == 1
    assert len(clusters[0].segment_ids) == 2


def test_load_osmconvert_poly_hcm() -> None:
    """City poly parses and covers central HCMC but not Hanoi."""
    from shapely.geometry import Point

    from gpx_osm_missing_paths.utils import load_osmconvert_poly

    poly = load_osmconvert_poly(Path("osm/hcm.poly"))
    assert poly.is_valid
    assert poly.covers(Point(106.70, 10.78))
    assert not poly.covers(Point(105.85, 21.03))
