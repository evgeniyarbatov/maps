import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from scripts.extract_pois import (
    extract_pois,
    node_tags,
    parse_nodes,
    tags_from_element,
    way_centroid,
)

SAMPLE_OSM = """<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="21.0000" lon="105.0000">
    <tag k="tourism" v="viewpoint"/>
    <tag k="name" v="Nui Dinh Viewpoint"/>
  </node>
  <node id="2" lat="21.0010" lon="105.0010">
    <tag k="shop" v="convenience"/>
  </node>
  <node id="3" lat="21.0020" lon="105.0020"/>
  <node id="4" lat="21.0030" lon="105.0030"/>
  <way id="10">
    <nd ref="3"/>
    <nd ref="4"/>
    <tag k="building" v="church"/>
    <tag k="name" v="Old Church"/>
  </way>
</osm>
"""


class ParseNodesTests(unittest.TestCase):
    def test_parses_node_id_to_lat_lon(self) -> None:
        root = ET.fromstring(SAMPLE_OSM)
        nodes = parse_nodes(root)
        self.assertEqual(nodes["1"], (21.0000, 105.0000))
        self.assertEqual(len(nodes), 4)


class NodeTagsTests(unittest.TestCase):
    def test_extracts_key_value_tags(self) -> None:
        root = ET.fromstring(SAMPLE_OSM)
        node = root.find("node")
        self.assertEqual(node_tags(node), {"tourism": "viewpoint", "name": "Nui Dinh Viewpoint"})


class TagsFromElementTests(unittest.TestCase):
    def test_extracts_tags_from_way(self) -> None:
        root = ET.fromstring(SAMPLE_OSM)
        way = root.find("way")
        self.assertEqual(tags_from_element(way), {"building": "church", "name": "Old Church"})


class WayCentroidTests(unittest.TestCase):
    def test_averages_referenced_node_coordinates(self) -> None:
        root = ET.fromstring(SAMPLE_OSM)
        nodes = parse_nodes(root)
        way = root.find("way")
        centroid = way_centroid(way, nodes)
        assert centroid is not None
        self.assertAlmostEqual(centroid[0], 21.0025)
        self.assertAlmostEqual(centroid[1], 105.0025)

    def test_returns_none_when_no_nodes_resolve(self) -> None:
        way = ET.fromstring('<way id="99"><nd ref="missing"/></way>')
        self.assertIsNone(way_centroid(way, {}))


class ExtractPoisTests(unittest.TestCase):
    def test_extracts_matching_nodes_and_ways_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            osm_path = Path(tmpdir) / "extract.osm"
            osm_path.write_text(SAMPLE_OSM, encoding="utf-8")

            pois = extract_pois(osm_path)

        ids = {poi["id"] for poi in pois}
        self.assertEqual(ids, {"node/1", "way/10"})

        viewpoint = next(poi for poi in pois if poi["id"] == "node/1")
        self.assertEqual(viewpoint["name"], "Nui Dinh Viewpoint")
        self.assertEqual(viewpoint["category"], "tourism=viewpoint")

        church = next(poi for poi in pois if poi["id"] == "way/10")
        self.assertEqual(church["category"], "building=church")
        self.assertAlmostEqual(church["lat"], 21.0025)

    def test_results_sorted_by_name_then_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            osm_path = Path(tmpdir) / "extract.osm"
            osm_path.write_text(SAMPLE_OSM, encoding="utf-8")

            pois = extract_pois(osm_path)

        names = [poi["name"].lower() for poi in pois]
        self.assertEqual(names, sorted(names))


if __name__ == "__main__":
    unittest.main()
