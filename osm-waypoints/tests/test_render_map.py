import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.render_map import load_waypoints


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
                mock.patch("scripts.render_map.POIS_RAW", raw),
                mock.patch("scripts.render_map.POIS_VALIDATED", validated),
            ):
                waypoints = load_waypoints()

        self.assertEqual([w["id"] for w in waypoints], ["keep"])

    def test_raises_when_neither_file_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            raw = Path(tmpdir) / "pois.json"
            validated = Path(tmpdir) / "pois_validated.json"

            with (
                mock.patch("scripts.render_map.POIS_RAW", raw),
                mock.patch("scripts.render_map.POIS_VALIDATED", validated),
                self.assertRaises(FileNotFoundError),
            ):
                load_waypoints()


if __name__ == "__main__":
    unittest.main()
