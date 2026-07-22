import unittest
from unittest import mock

from scripts.validate_pois import classify_poi


class ClassifyPoiTests(unittest.TestCase):
    def test_marks_poi_valid_from_model_verdict(self) -> None:
        poi = {"name": "Old Pagoda", "category": "building=pagoda", "tags": {}}

        with mock.patch(
            "scripts.validate_pois.generate_json",
            return_value={"valid": True, "reason": "notable landmark"},
        ):
            result = classify_poi(poi, model="mistral-nemo")

        self.assertTrue(result["valid"])
        self.assertEqual(result["validation_reason"], "notable landmark")
        self.assertEqual(result["name"], "Old Pagoda")

    def test_marks_poi_invalid_from_model_verdict(self) -> None:
        poi = {"name": "Corner Shop", "category": "shop=convenience", "tags": {}}

        with mock.patch(
            "scripts.validate_pois.generate_json",
            return_value={"valid": False, "reason": "not walk-relevant"},
        ):
            result = classify_poi(poi, model="mistral-nemo")

        self.assertFalse(result["valid"])
        self.assertEqual(result["validation_reason"], "not walk-relevant")

    def test_falls_back_to_error_reason_when_no_reason_given(self) -> None:
        poi = {"name": "Unclear", "category": "x=y", "tags": {}}

        with mock.patch(
            "scripts.validate_pois.generate_json",
            return_value={"error": "unparseable model response"},
        ):
            result = classify_poi(poi, model="mistral-nemo")

        self.assertFalse(result["valid"])
        self.assertEqual(result["validation_reason"], "unparseable model response")


if __name__ == "__main__":
    unittest.main()
