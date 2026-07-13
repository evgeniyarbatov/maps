import unittest

from scripts import extract_photo_locations as epl


class ExtractPhotoLocationsTests(unittest.TestCase):
    def test_to_float_tuple(self) -> None:
        self.assertEqual(epl.to_float((1, 4)), 0.25)

    def test_to_float_number(self) -> None:
        self.assertEqual(epl.to_float(2.5), 2.5)

    def test_dms_to_decimal_north(self) -> None:
        value = ((40, 1), (30, 1), (0, 1))
        self.assertAlmostEqual(epl.dms_to_decimal(value, "N"), 40.5)

    def test_dms_to_decimal_west(self) -> None:
        value = ((74, 1), (0, 1), (0, 1))
        self.assertAlmostEqual(epl.dms_to_decimal(value, "W"), -74.0)

    def test_dms_to_decimal_east(self) -> None:
        value = ((120, 1), (30, 1), (0, 1))
        self.assertAlmostEqual(epl.dms_to_decimal(value, "E"), 120.5)

    def test_extract_gps_missing_tag(self) -> None:
        self.assertIsNone(epl.extract_gps({}))

    def test_extract_gps_reads_exif(self) -> None:
        exif = {
            epl.GPS_TAG_ID: {
                1: "N",
                2: ((37, 1), (48, 1), (0, 1)),
                3: "W",
                4: ((122, 1), (24, 1), (0, 1)),
            }
        }
        gps = epl.extract_gps(exif)
        self.assertIsNotNone(gps)
        assert gps is not None
        lat, lon = gps
        self.assertAlmostEqual(lat, 37.8)
        self.assertAlmostEqual(lon, -122.4)


if __name__ == "__main__":
    unittest.main()
