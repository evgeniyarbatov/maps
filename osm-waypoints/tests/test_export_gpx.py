import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.export_gpx import build_gpx, load_waypoints, prettify_xml

SAMPLE_WAYPOINT = {
    "id": "node/1",
    "name": "Núi Đinh Viewpoint",
    "lat": 21.12345,
    "lon": 105.6789,
    "ele": 210.4,
    "category": "tourism=viewpoint",
    "tags": {},
    "description": "Forest viewpoint",
}


class BuildGpxTests(unittest.TestCase):
    def test_builds_wpt_with_expected_fields(self) -> None:
        gpx = build_gpx([SAMPLE_WAYPOINT])
        wpt = gpx.find("wpt")

        self.assertEqual(wpt.get("lat"), "21.1234500")
        self.assertEqual(wpt.get("lon"), "105.6789000")
        self.assertEqual(wpt.find("name").text, "Nui Dinh Viewpoint")
        self.assertEqual(wpt.find("desc").text, "Forest viewpoint")
        self.assertEqual(wpt.find("sym").text, "Scenic Area")
        self.assertEqual(wpt.find("ele").text, "210.4")

    def test_falls_back_to_category_when_description_missing(self) -> None:
        waypoint = {**SAMPLE_WAYPOINT, "description": ""}
        gpx = build_gpx([waypoint])
        wpt = gpx.find("wpt")
        self.assertEqual(wpt.find("desc").text, "tourism=viewpoint")

    def test_omits_ele_when_none(self) -> None:
        waypoint = {**SAMPLE_WAYPOINT, "ele": None}
        gpx = build_gpx([waypoint])
        wpt = gpx.find("wpt")
        self.assertIsNone(wpt.find("ele"))


class PrettifyXmlTests(unittest.TestCase):
    def test_produces_indented_xml_with_declaration(self) -> None:
        gpx = build_gpx([SAMPLE_WAYPOINT])
        xml_text = prettify_xml(gpx)
        self.assertTrue(xml_text.startswith("<?xml"))
        self.assertIn("<wpt", xml_text)


class LoadWaypointsTests(unittest.TestCase):
    def test_prefers_validated_file_and_filters_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            raw = Path(tmpdir) / "pois.json"
            validated = Path(tmpdir) / "pois_validated.json"
            raw.write_text(json.dumps({"waypoints": [{"id": "raw", "valid": True}]}))
            validated.write_text(
                json.dumps(
                    {
                        "waypoints": [
                            {"id": "keep", "valid": True},
                            {"id": "drop", "valid": False},
                        ]
                    }
                )
            )

            with (
                mock.patch("scripts.export_gpx.POIS_RAW", raw),
                mock.patch("scripts.export_gpx.POIS_VALIDATED", validated),
            ):
                waypoints = load_waypoints()

        self.assertEqual([w["id"] for w in waypoints], ["keep"])

    def test_falls_back_to_raw_file_when_validated_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            raw = Path(tmpdir) / "pois.json"
            validated = Path(tmpdir) / "pois_validated.json"
            raw.write_text(json.dumps({"waypoints": [{"id": "raw"}]}))

            with (
                mock.patch("scripts.export_gpx.POIS_RAW", raw),
                mock.patch("scripts.export_gpx.POIS_VALIDATED", validated),
            ):
                waypoints = load_waypoints()

        self.assertEqual([w["id"] for w in waypoints], ["raw"])

    def test_raises_when_neither_file_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            raw = Path(tmpdir) / "pois.json"
            validated = Path(tmpdir) / "pois_validated.json"

            with (
                mock.patch("scripts.export_gpx.POIS_RAW", raw),
                mock.patch("scripts.export_gpx.POIS_VALIDATED", validated),
                self.assertRaises(FileNotFoundError),
            ):
                load_waypoints()


if __name__ == "__main__":
    unittest.main()
