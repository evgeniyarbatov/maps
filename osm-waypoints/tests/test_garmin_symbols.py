import unittest

from scripts.garmin_symbols import garmin_symbol


class GarminSymbolTests(unittest.TestCase):
    def test_direct_category_lookup(self) -> None:
        self.assertEqual(garmin_symbol("tourism=viewpoint"), "Scenic Area")
        self.assertEqual(garmin_symbol("natural=peak"), "Summit")
        self.assertEqual(garmin_symbol("man_made=water_well"), "Drinking Water")

    def test_historic_category_uses_historic_tag(self) -> None:
        self.assertEqual(garmin_symbol("historic=memorial", {"historic": "memorial"}), "Bell")
        self.assertEqual(garmin_symbol("historic=ruins", {"historic": "ruins"}), "Mine")
        self.assertEqual(
            garmin_symbol("historic=battlefield", {"historic": "battlefield"}), "Flag, Red"
        )

    def test_historic_category_falls_back_to_category_suffix(self) -> None:
        self.assertEqual(garmin_symbol("historic=tomb"), "Cemetery")

    def test_historic_unknown_type_defaults_to_building(self) -> None:
        self.assertEqual(garmin_symbol("historic=unknown_type"), "Building")

    def test_place_of_worship_christian_religion(self) -> None:
        self.assertEqual(
            garmin_symbol("amenity=place_of_worship", {"religion": "christian"}), "Church"
        )
        self.assertEqual(
            garmin_symbol("amenity=place_of_worship", {"religion": "Catholic"}), "Church"
        )

    def test_place_of_worship_by_building_tag(self) -> None:
        self.assertEqual(
            garmin_symbol("amenity=place_of_worship", {"building": "chapel"}), "Church"
        )

    def test_place_of_worship_muslim(self) -> None:
        self.assertEqual(
            garmin_symbol("amenity=place_of_worship", {"religion": "muslim"}), "Building"
        )
        self.assertEqual(
            garmin_symbol("amenity=place_of_worship", {"building": "mosque"}), "Building"
        )

    def test_place_of_worship_eastern_religions(self) -> None:
        self.assertEqual(
            garmin_symbol("amenity=place_of_worship", {"religion": "buddhist"}), "Building"
        )
        self.assertEqual(
            garmin_symbol("amenity=place_of_worship", {"building": "pagoda"}), "Building"
        )

    def test_place_of_worship_unknown_religion_defaults_to_building(self) -> None:
        self.assertEqual(
            garmin_symbol("amenity=place_of_worship", {"religion": "unknown"}), "Building"
        )
        self.assertEqual(garmin_symbol("amenity=place_of_worship"), "Building")

    def test_keyword_fallback_tower(self) -> None:
        self.assertEqual(garmin_symbol("some=tower_thing", {"man_made": "tower"}), "Tall Tower")
        self.assertEqual(garmin_symbol("some=tower_thing"), "Short Tower")

    def test_keyword_fallback_peak_and_viewpoint(self) -> None:
        self.assertEqual(garmin_symbol("some=summit_marker"), "Summit")
        self.assertEqual(garmin_symbol("some=scenic_overlook"), "Scenic Area")

    def test_keyword_fallback_museum_picnic_cave_church(self) -> None:
        self.assertEqual(garmin_symbol("some=museum_annex"), "Museum")
        self.assertEqual(garmin_symbol("some=picnic_area"), "Picnic Area")
        self.assertEqual(garmin_symbol("some=cave_system"), "Tunnel")
        self.assertEqual(garmin_symbol("some=worship_hall"), "Church")

    def test_unmatched_category_defaults_to_blue_flag(self) -> None:
        self.assertEqual(garmin_symbol("shop=convenience"), "Flag, Blue")


if __name__ == "__main__":
    unittest.main()
