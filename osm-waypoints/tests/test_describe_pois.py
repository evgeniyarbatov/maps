import unittest
from unittest import mock

from scripts.describe_pois import describe_poi


class DescribePoiTests(unittest.TestCase):
    def test_returns_normalized_model_description(self) -> None:
        poi = {"category": "natural=peak", "name": "Peak", "tags": {"ele": "491"}}

        with mock.patch(
            "scripts.describe_pois.generate_json",
            return_value={"description": "491 m peak."},
        ):
            description = describe_poi(poi, model="mistral-nemo")

        self.assertEqual(description, "491 m peak")

    def test_returns_empty_string_when_model_gives_no_description(self) -> None:
        poi = {"category": "x=y", "name": "z", "tags": {}}

        with mock.patch("scripts.describe_pois.generate_json", return_value={}):
            description = describe_poi(poi, model="mistral-nemo")

        self.assertEqual(description, "")


if __name__ == "__main__":
    unittest.main()
