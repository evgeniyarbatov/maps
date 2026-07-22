import tempfile
import unittest
from pathlib import Path

from scripts.gpx_utils import compute_convex_polygon_with_buffer, load_track_points

SIMPLE_GPX = """<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="test">
  <trk>
    <name>T</name>
    <trkseg>
      <trkpt lat="21.0000" lon="105.0000"></trkpt>
      <trkpt lat="21.0100" lon="105.0100"></trkpt>
    </trkseg>
  </trk>
  <rte>
    <rtept lat="21.0200" lon="105.0050"></rtept>
  </rte>
  <wpt lat="21.0050" lon="105.0150"></wpt>
</gpx>
"""


class LoadTrackPointsTests(unittest.TestCase):
    def test_loads_track_route_and_waypoints_from_all_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            gpx_dir = Path(tmpdir)
            (gpx_dir / "a.gpx").write_text(SIMPLE_GPX, encoding="utf-8")

            points = load_track_points(gpx_dir)

        self.assertEqual(len(points), 4)
        self.assertIn((105.0000, 21.0000), points)
        self.assertIn((105.0150, 21.0050), points)

    def test_raises_when_no_gpx_files_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, self.assertRaises(ValueError):
            load_track_points(Path(tmpdir))


class ComputeConvexPolygonWithBufferTests(unittest.TestCase):
    def test_returns_polygon_containing_original_points(self) -> None:
        points = [
            (105.0000, 21.0000),
            (105.0100, 21.0000),
            (105.0100, 21.0100),
            (105.0000, 21.0100),
        ]

        polygon = compute_convex_polygon_with_buffer(points, buffer_km=0.25)

        self.assertEqual(polygon.geom_type, "Polygon")
        min_lon, min_lat, max_lon, max_lat = polygon.bounds
        self.assertLess(min_lon, 105.0000)
        self.assertGreater(max_lon, 105.0100)
        self.assertLess(min_lat, 21.0000)
        self.assertGreater(max_lat, 21.0100)

    def test_larger_buffer_produces_larger_polygon(self) -> None:
        points = [(105.0, 21.0), (105.01, 21.0), (105.01, 21.01), (105.0, 21.01)]

        small = compute_convex_polygon_with_buffer(points, buffer_km=0.1)
        large = compute_convex_polygon_with_buffer(points, buffer_km=1.0)

        self.assertGreater(large.area, small.area)


if __name__ == "__main__":
    unittest.main()
