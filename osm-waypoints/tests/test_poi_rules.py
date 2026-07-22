import unittest

from scripts.poi_rules import category_label, matches_poi, poi_display_name


class MatchesPoiTests(unittest.TestCase):
    def test_matches_exact_key_value_rule(self) -> None:
        self.assertEqual(matches_poi({"tourism": "viewpoint"}), "tourism=viewpoint")
        self.assertEqual(matches_poi({"natural": "peak"}), "natural=peak")

    def test_matches_wildcard_rule_returns_actual_value(self) -> None:
        self.assertEqual(matches_poi({"historic": "monument"}), "historic=monument")

    def test_non_matching_value_for_known_key_is_rejected(self) -> None:
        self.assertIsNone(matches_poi({"tourism": "hotel"}))

    def test_no_relevant_tags_returns_none(self) -> None:
        self.assertIsNone(matches_poi({"shop": "convenience"}))

    def test_empty_tags_returns_none(self) -> None:
        self.assertIsNone(matches_poi({}))

    def test_first_matching_rule_wins(self) -> None:
        self.assertEqual(
            matches_poi({"tourism": "viewpoint", "natural": "peak"}), "tourism=viewpoint"
        )


class CategoryLabelTests(unittest.TestCase):
    def test_strips_key_and_titlecases(self) -> None:
        self.assertEqual(category_label("tourism=viewpoint"), "Viewpoint")

    def test_replaces_underscores(self) -> None:
        self.assertEqual(category_label("tourism=picnic_site"), "Picnic Site")


class PoiDisplayNameTests(unittest.TestCase):
    def test_prefers_name_en(self) -> None:
        tags = {"name:en": "English Name", "name": "Local Name"}
        self.assertEqual(poi_display_name(tags, "tourism=viewpoint"), "English Name")

    def test_falls_back_to_name(self) -> None:
        tags = {"name": "Local Name"}
        self.assertEqual(poi_display_name(tags, "tourism=viewpoint"), "Local Name")

    def test_falls_back_to_alt_name_then_official_name(self) -> None:
        self.assertEqual(poi_display_name({"alt_name": "Alt"}, "tourism=viewpoint"), "Alt")
        self.assertEqual(
            poi_display_name({"official_name": "Official"}, "tourism=viewpoint"), "Official"
        )

    def test_falls_back_to_category_label_when_no_name_tags(self) -> None:
        self.assertEqual(poi_display_name({}, "tourism=viewpoint"), "Viewpoint")


if __name__ == "__main__":
    unittest.main()
