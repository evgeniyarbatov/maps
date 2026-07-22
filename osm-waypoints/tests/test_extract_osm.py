import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from shapely.geometry import Polygon

from scripts.extract_osm import extract_with_osmium, write_polygon_geojson


class WritePolygonGeojsonTests(unittest.TestCase):
    def test_writes_feature_with_buffer_property_and_geometry(self) -> None:
        polygon = Polygon([(105.0, 21.0), (105.1, 21.0), (105.1, 21.1), (105.0, 21.1)])

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "nested" / "polygon.geojson"
            write_polygon_geojson(polygon, output_path)

            feature = json.loads(output_path.read_text())

        self.assertEqual(feature["type"], "Feature")
        self.assertEqual(feature["geometry"]["type"], "Polygon")
        self.assertIn("buffer_km", feature["properties"])


class ExtractWithOsmiumTests(unittest.TestCase):
    def test_invokes_osmium_with_expected_args(self) -> None:
        with mock.patch("scripts.extract_osm.subprocess.run") as mock_run:
            extract_with_osmium(
                Path("source.pbf"), Path("polygon.geojson"), Path("out/extract.osm")
            )

        args = mock_run.call_args.args[0]
        self.assertEqual(args[0], "osmium")
        self.assertIn("source.pbf", args)
        self.assertIn("polygon.geojson", args)
        self.assertIn(str(Path("out/extract.osm")), args)
        self.assertEqual(mock_run.call_args.kwargs["check"], True)


if __name__ == "__main__":
    unittest.main()
