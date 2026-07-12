"""Long traces must be cut into street-sized chunks before clustering/coverage checks."""

from gpx_osm_missing_paths.gpx_processor import _split_points_by_distance
from gpx_osm_missing_paths.utils import haversine_m

LON_PER_100M = 0.0009  # roughly 100m eastward at the equator


def _points(n: int) -> list[tuple[float, float, None]]:
    return [(LON_PER_100M * i, 0.0, None) for i in range(n)]


def test_short_trace_is_a_single_chunk() -> None:
    points = _points(6)  # ~500m
    chunks = _split_points_by_distance(points, chunk_length_m=750.0)
    assert len(chunks) == 1
    assert chunks[0] == points


def test_long_trace_splits_into_multiple_chunks() -> None:
    points = _points(301)  # ~30km
    chunks = _split_points_by_distance(points, chunk_length_m=750.0)

    assert len(chunks) > 5
    for chunk in chunks:
        length_m = sum(
            haversine_m(chunk[i][0], chunk[i][1], chunk[i + 1][0], chunk[i + 1][1])
            for i in range(len(chunk) - 1)
        )
        assert length_m <= 850.0  # chunk_length_m plus one point's worth of slack


def test_consecutive_chunks_share_boundary_point() -> None:
    points = _points(50)
    chunks = _split_points_by_distance(points, chunk_length_m=200.0)
    assert len(chunks) > 1
    for a, b in zip(chunks, chunks[1:], strict=False):
        assert a[-1] == b[0]


def test_empty_and_single_point_inputs() -> None:
    assert _split_points_by_distance([], chunk_length_m=750.0) == []
    single = [(0.0, 0.0, None)]
    assert _split_points_by_distance(single, chunk_length_m=750.0) == [single]
