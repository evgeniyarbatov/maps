import unittest

from scripts.osm_context import build_description_context, parse_elevation


class ParseElevationTests(unittest.TestCase):
    def test_parses_ele_tag(self) -> None:
        self.assertEqual(parse_elevation({"ele": "491"}), 491.0)

    def test_parses_ele_tag_with_unit_suffix(self) -> None:
        self.assertEqual(parse_elevation({"ele": "491 m"}), 491.0)

    def test_falls_back_to_elevation_tag(self) -> None:
        self.assertEqual(parse_elevation({"elevation": "120"}), 120.0)

    def test_falls_back_to_node_ele_when_no_tags(self) -> None:
        self.assertEqual(parse_elevation({}, node_ele=55.0), 55.0)

    def test_unparseable_value_falls_back_to_node_ele(self) -> None:
        self.assertEqual(parse_elevation({"ele": "unknown"}, node_ele=10.0), 10.0)

    def test_returns_none_when_nothing_available(self) -> None:
        self.assertIsNone(parse_elevation({}))


class BuildDescriptionContextTests(unittest.TestCase):
    def test_includes_category_and_display_name(self) -> None:
        poi = {"category": "tourism=viewpoint", "name": "Nui Dinh Viewpoint", "tags": {}}
        context = build_description_context(poi)
        self.assertEqual(context["category"], "tourism=viewpoint")
        self.assertEqual(context["display_name"], "Nui Dinh Viewpoint")

    def test_includes_elevation_when_present(self) -> None:
        poi = {"category": "natural=peak", "name": "Peak", "tags": {"ele": "491"}}
        context = build_description_context(poi)
        self.assertEqual(context["elevation_m"], 491.0)

    def test_includes_coordinates_when_lat_lon_present(self) -> None:
        poi = {"category": "x", "name": "y", "tags": {}, "lat": 21.12345, "lon": 105.6789}
        context = build_description_context(poi)
        self.assertEqual(context["coordinates"], "21.12345, 105.67890")

    def test_includes_direct_tags_when_non_empty(self) -> None:
        poi = {
            "category": "tourism=museum",
            "name": "Museum",
            "tags": {"wikipedia": "en:Some Museum", "religion": ""},
        }
        context = build_description_context(poi)
        self.assertEqual(context["wikipedia"], "en:Some Museum")
        self.assertNotIn("religion", context)

    def test_includes_extra_prefixed_tags_not_in_direct_list(self) -> None:
        poi = {
            "category": "tourism=museum",
            "name": "Museum",
            "tags": {"name:fr": "Musee", "addr:district": "District 1"},
        }
        context = build_description_context(poi)
        self.assertEqual(context["name:fr"], "Musee")
        self.assertEqual(context["addr:district"], "District 1")

    def test_omits_empty_and_missing_tags(self) -> None:
        poi = {"category": "x", "name": "y", "tags": {"note": "  "}}
        context = build_description_context(poi)
        self.assertNotIn("note", context)


if __name__ == "__main__":
    unittest.main()
