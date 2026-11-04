import math
import sys
import tempfile
import time
import unittest
from pathlib import Path

import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import find_loops as fl

M_PER_DEG = 111_195.0


def with_lengths(H: nx.Graph, step_m: float) -> nx.Graph:
    for u, v in H.edges:
        H[u][v]["length"] = step_m
    return H


def grid(n: int, step_m: float) -> nx.Graph:
    H = nx.convert_node_labels_to_integers(nx.grid_2d_graph(n, n), label_attribute="rc")
    for _, data in H.nodes(data=True):
        r, c = data["rc"]
        data["y"], data["x"] = r * step_m / M_PER_DEG, c * step_m / M_PER_DEG
    return with_lengths(H, step_m)


def is_simple_cycle(H: nx.Graph, loop: list[int]) -> bool:
    return (
        loop[0] == loop[-1]
        and len(set(loop[:-1])) == len(loop) - 1
        and all(H.has_edge(u, v) for u, v in zip(loop, loop[1:], strict=False))
    )


def path_length(H: nx.Graph, loop: list[int]) -> float:
    return sum(H[u][v]["length"] for u, v in zip(loop, loop[1:], strict=False))


def add_ring(
    H: nx.Graph,
    ids: list[int],
    coords: list[tuple[float, float]],
    edge_m: float,
    grade: int = 0,
) -> None:
    for node, (lat, lon) in zip(ids, coords, strict=True):
        H.add_node(node, y=lat, x=lon)
    for a, b in zip(ids, [*ids[1:], ids[0]], strict=True):
        H.add_edge(a, b, length=edge_m, grade=grade)


def load_osm(body: str, roads: list[fl.RoadSeg] | None = None) -> nx.MultiDiGraph:
    xml = f'<?xml version="1.0" encoding="UTF-8"?>\n<osm version="0.6">\n{body}</osm>\n'
    with tempfile.NamedTemporaryFile("w", suffix=".osm") as handle:
        handle.write(xml)
        handle.flush()
        return fl.load_footpath_graph(Path(handle.name), 10.77, 106.69, 5_000.0, roads or ())


class RoadCrossingTest(unittest.TestCase):
    def test_open_segments_cross_only_at_a_proper_intersection(self) -> None:
        self.assertTrue(fl.segments_cross((0.0, 0.0), (2.0, 2.0), (0.0, 2.0), (2.0, 0.0)))
        self.assertFalse(fl.segments_cross((0.0, 0.0), (1.0, 0.0), (1.0, 0.0), (1.0, 1.0)))
        self.assertFalse(fl.segments_cross((0.0, 0.0), (2.0, 0.0), (1.0, 0.0), (3.0, 0.0)))

    def test_same_grade_road_blocks_a_segment(self) -> None:
        road = fl.RoadSeg(0.0, 0.0, 0.0, 2.0, 0)
        self.assertTrue(fl.segment_crosses_road(-1.0, 1.0, 1.0, 1.0, 0, [road]))
        self.assertTrue(fl.segment_crosses_road(1.0, 1.0, 0.0, 1.0, 0, [road]))
        self.assertFalse(fl.segment_crosses_road(0.0, 0.0, 1.0, 0.0, 0, [road]))
        self.assertFalse(fl.segment_crosses_road(-1.0, 1.0, 1.0, 1.0, 1, [road]))

    def test_crossing_tags(self) -> None:
        self.assertTrue(fl.is_crossing_way({"footway": "crossing"}))
        self.assertTrue(fl.is_crossing_way({"footway": "traffic_island"}))
        self.assertTrue(fl.is_crossing_way({"crossing": "marked"}))
        self.assertFalse(fl.is_crossing_way({"crossing": "no", "footway": "sidewalk"}))

    def test_mapped_crossing_is_not_loaded(self) -> None:
        graph = load_osm(
            """
  <node id="1" lat="10.770" lon="106.690"/>
  <node id="2" lat="10.771" lon="106.690"/>
  <way id="10">
    <nd ref="1"/><nd ref="2"/>
    <tag k="highway" v="footway"/>
    <tag k="footway" v="crossing"/>
  </way>
"""
        )
        self.assertEqual(graph.number_of_edges(), 0)

    def test_segment_that_cuts_a_road_is_not_loaded(self) -> None:
        road = [fl.RoadSeg(10.771, 106.690, 10.771, 106.692, 0)]
        graph = load_osm(
            """
  <node id="1" lat="10.770" lon="106.691"/>
  <node id="2" lat="10.772" lon="106.691"/>
  <way id="10">
    <nd ref="1"/><nd ref="2"/>
    <tag k="highway" v="footway"/>
  </way>
""",
            road,
        )
        self.assertEqual(graph.number_of_edges(), 0)

    def test_shared_endpoint_and_bridge_are_loaded(self) -> None:
        road = [fl.RoadSeg(10.771, 106.690, 10.771, 106.692, 0)]
        shared = load_osm(
            """
  <node id="1" lat="10.771" lon="106.690"/>
  <node id="2" lat="10.773" lon="106.690"/>
  <way id="10">
    <nd ref="1"/><nd ref="2"/>
    <tag k="highway" v="footway"/>
    <tag k="footway" v="sidewalk"/>
  </way>
""",
            road,
        )
        bridge = load_osm(
            """
  <node id="1" lat="10.770" lon="106.691"/>
  <node id="2" lat="10.772" lon="106.691"/>
  <way id="10">
    <nd ref="1"/><nd ref="2"/>
    <tag k="highway" v="footway"/>
    <tag k="bridge" v="yes"/>
  </way>
""",
            road,
        )
        self.assertEqual(shared.number_of_edges(), 1)
        self.assertEqual(bridge.number_of_edges(), 1)

    def test_road_arms_point_at_the_other_end(self) -> None:
        self.assertEqual(fl.way_grade({"layer": "2", "bridge": "yes"}), 2)
        self.assertEqual(fl.way_grade({"tunnel": "yes"}), -1)
        self.assertEqual(fl.way_grade({"layer": "nope"}), 0)
        with tempfile.NamedTemporaryFile("w", suffix=".osm") as handle:
            handle.write(
                """<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="10.770" lon="106.690"/>
  <node id="2" lat="10.770" lon="106.691"/>
  <node id="3" lat="10.772" lon="106.690"/>
  <node id="4" lat="10.772" lon="106.691"/>
  <way id="10">
    <nd ref="1"/><nd ref="2"/>
    <tag k="highway" v="residential"/>
  </way>
  <way id="11">
    <nd ref="3"/><nd ref="4"/>
    <tag k="highway" v="primary"/>
    <tag k="bridge" v="yes"/>
  </way>
</osm>
"""
            )
            handle.flush()
            segments, arms = fl.load_road_network(Path(handle.name))
        self.assertEqual(sorted(segment.grade for segment in segments), [0, 1])
        self.assertEqual(arms[1], (fl.RoadArm(10.770, 106.691, 0),))
        self.assertEqual(arms[2][0].grade, 0)
        self.assertEqual(arms[3][0].grade, 1)

    def test_opposite_sides_of_a_road_are_dropped(self) -> None:
        graph = nx.Graph()
        add_ring(
            graph,
            [1, 2, 3, 4],
            [(0.0, 0.0), (0.002, 0.0), (0.0, -0.002), (-0.002, 0.0)],
            220.0,
        )
        add_ring(
            graph,
            [5, 6, 7, 8],
            [(1.0, 1.0), (1.0, 1.002), (1.002, 1.002), (1.002, 1.0)],
            200.0,
        )
        arms = {1: (fl.RoadArm(0.0, 0.002, 0),)}
        self.assertTrue(fl.loop_crosses_road(graph, [1, 2, 3, 4, 1], arms))
        loops = fl.find_loops(graph, 883.0, 100.0, 10, 1.0, road_arms=arms)
        self.assertEqual([length for _, length in loops], [800.0])

    def test_corner_along_a_road_is_kept(self) -> None:
        graph = nx.Graph()
        add_ring(
            graph,
            [1, 2, 3, 4],
            [(0.0, 0.0), (0.002, 0.0), (0.002, 0.002), (0.0, 0.002)],
            220.0,
        )
        arms = {1: (fl.RoadArm(0.0, 0.003, 0),)}
        self.assertFalse(fl.loop_crosses_road(graph, [1, 2, 3, 4, 1], arms))
        loops = fl.find_loops(graph, 883.0, 100.0, 10, 1.0, road_arms=arms)
        self.assertEqual([length for _, length in loops], [880.0])

    def test_bridge_over_a_road_is_kept(self) -> None:
        graph = nx.Graph()
        add_ring(
            graph,
            [1, 2, 3, 4],
            [(0.0, 0.0), (0.002, 0.0), (0.0, -0.002), (-0.002, 0.0)],
            220.0,
            grade=1,
        )
        arms = {1: (fl.RoadArm(0.0, 0.002, 0),)}
        self.assertFalse(fl.loop_crosses_road(graph, [1, 2, 3, 4, 1], arms))
        loops = fl.find_loops(graph, 883.0, 100.0, 10, 1.0, road_arms=arms)
        self.assertEqual([length for _, length in loops], [880.0])


class FindLoopsTest(unittest.TestCase):
    def test_unit_squares_found_once_each(self) -> None:
        H = grid(3, 100.0)
        loops = fl.find_loops(H, 400.0, 1.0, 500, 1.0)
        self.assertEqual(len(loops), 4)
        for loop, length in loops:
            self.assertTrue(is_simple_cycle(H, loop))
            self.assertAlmostEqual(length, 400.0)
            self.assertAlmostEqual(path_length(H, loop), length)

    def test_length_window(self) -> None:
        H = grid(3, 100.0)
        loops = fl.find_loops(H, 600.0, 1.0, 500, 1.0)
        self.assertEqual(len(loops), 4)
        for loop, length in loops:
            self.assertTrue(is_simple_cycle(H, loop))
            self.assertAlmostEqual(length, 600.0)

    def test_matches_networkx_cycle_count(self) -> None:
        H = grid(4, 100.0)
        expected = sum(
            1 for c in nx.simple_cycles(H) if len(c) >= 3 and 800 <= 100.0 * len(c) <= 1000
        )
        loops = fl.find_loops(H, 900.0, 100.0, 10_000, 1.0)
        self.assertEqual(len(loops), expected)
        self.assertTrue(all(is_simple_cycle(H, loop) for loop, _ in loops))

    def test_ring_without_junctions(self) -> None:
        H = with_lengths(nx.cycle_graph(10), 90.0)
        for i, node in enumerate(H.nodes):
            angle = 2 * math.pi * i / 10
            H.nodes[node]["y"] = math.sin(angle) * 0.001
            H.nodes[node]["x"] = math.cos(angle) * 0.001
        loops = fl.find_loops(H, 900.0, 10.0, 500, 1.0)
        self.assertEqual(len(loops), 1)
        self.assertTrue(is_simple_cycle(H, loops[0][0]))

    def test_closest_first(self) -> None:
        loops = fl.find_loops(grid(3, 100.0), 500.0, 100.0, 500, 1.0)
        diffs = [abs(length - 500.0) for _, length in loops]
        self.assertEqual(diffs, sorted(diffs))

    def test_overlap_drops_near_duplicates(self) -> None:
        all_loops = fl.find_loops(grid(4, 100.0), 900.0, 100.0, 10_000, 1.0)
        distinct = fl.find_loops(grid(4, 100.0), 900.0, 100.0, 10_000, 0.5)
        self.assertLess(len(distinct), len(all_loops))

    def test_max_loops_cap(self) -> None:
        self.assertEqual(len(fl.find_loops(grid(4, 100.0), 400.0, 1.0, 3, 1.0)), 3)

    def test_dense_grid_finishes_with_valid_loops(self) -> None:
        H = grid(8, 25.0)
        started = time.perf_counter()
        loops = fl.find_loops(H, 500.0, 50.0, 20, 0.5)
        self.assertLess(time.perf_counter() - started, 10.0)
        self.assertGreater(len(loops), 0)
        self.assertLessEqual(len(loops), 20)
        for loop, length in loops:
            self.assertTrue(is_simple_cycle(H, loop))
            self.assertLessEqual(abs(length - 500.0), 50.0)
            self.assertAlmostEqual(path_length(H, loop), length)

    def test_fewer_turns_ranks_ahead_of_a_closer_length(self) -> None:
        H = nx.Graph()

        def add_cycle(ids: list[int], coords: list[tuple[float, float]], edge_m: float) -> None:
            for node, (lat, lon) in zip(ids, coords, strict=True):
                H.add_node(node, y=lat, x=lon)
            for a, b in zip(ids, [*ids[1:], ids[0]], strict=True):
                H.add_edge(a, b, length=edge_m)

        side = 0.001
        add_cycle([1, 2, 3, 4], [(0.0, 0.0), (0.0, side), (side, side), (side, 0.0)], 200.0)
        origin = 1.0
        add_cycle(
            [5, 6, 7, 8, 9, 10],
            [
                (origin, origin),
                (origin, origin + side),
                (origin + side, origin + side),
                (origin + side, origin + 0.5 * side),
                (origin + 2 * side, origin + 0.5 * side),
                (origin + 2 * side, origin),
            ],
            880.0 / 6.0,
        )
        loops = fl.find_loops(H, 883.0, 100.0, 10, 1.0)
        self.assertEqual(len(loops), 2)
        self.assertAlmostEqual(loops[0][1], 800.0)
        self.assertAlmostEqual(loops[1][1], 880.0)
        self.assertEqual(fl.turn_count(H, loops[0][0]), 4)
        self.assertEqual(fl.turn_count(H, loops[1][0]), 6)

    def test_straight_shape_point_is_not_a_turn(self) -> None:
        H = nx.Graph()
        H.add_node(1, y=0.0, x=0.0)
        H.add_node(2, y=0.0, x=0.001)
        H.add_node(3, y=0.001, x=0.001)
        H.add_node(4, y=0.001, x=0.0005)
        H.add_node(5, y=0.001, x=0.0)
        self.assertEqual(fl.turn_count(H, [1, 2, 3, 4, 5, 1]), 4)

    def test_park_loop_ranks_ahead_of_closer_street_loop(self) -> None:
        H = nx.Graph()

        def add_square(ids: list[int], coords: list[tuple[float, float]], edge_m: float) -> None:
            for node, (lat, lon) in zip(ids, coords, strict=True):
                H.add_node(node, y=lat, x=lon)
            for a, b in zip(ids, [*ids[1:], ids[0]], strict=True):
                H.add_edge(a, b, length=edge_m)

        add_square([1, 2, 3, 4], [(1.0, 1.0), (1.0, 1.001), (1.001, 1.001), (1.001, 1.0)], 220.0)
        add_square(
            [5, 6, 7, 8],
            [(0.001, 0.001), (0.001, 0.002), (0.002, 0.002), (0.002, 0.001)],
            200.0,
        )
        plain = fl.find_loops(H, 883.0, 100.0, 10, 1.0)
        self.assertEqual([length for _, length in plain], [880.0, 800.0])
        ring = ((0.0, 0.0), (0.0, 0.003), (0.003, 0.003), (0.003, 0.0), (0.0, 0.0))
        parked = fl.find_loops(H, 883.0, 100.0, 10, 1.0, [fl.Park(outers=(ring,))])
        self.assertEqual([length for _, length in parked], [800.0, 880.0])

    def test_park_hole_is_outside(self) -> None:
        park = fl.Park(
            outers=(((0.0, 0.0), (0.0, 3.0), (3.0, 3.0), (3.0, 0.0), (0.0, 0.0)),),
            inners=(((1.0, 1.0), (1.0, 2.0), (2.0, 2.0), (2.0, 1.0), (1.0, 1.0)),),
        )
        self.assertTrue(fl.point_in_parks(0.5, 0.5, [park]))
        self.assertFalse(fl.point_in_parks(1.5, 1.5, [park]))
        self.assertFalse(fl.point_in_parks(4.0, 4.0, [park]))

    def test_multipolygon_outers_are_stitched(self) -> None:
        osm = """<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="0" lon="0"/>
  <node id="2" lat="0" lon="2"/>
  <node id="3" lat="2" lon="2"/>
  <node id="4" lat="2" lon="0"/>
  <way id="10"><nd ref="1"/><nd ref="2"/><nd ref="3"/></way>
  <way id="11"><nd ref="3"/><nd ref="4"/><nd ref="1"/></way>
  <relation id="99">
    <member type="way" ref="10" role="outer"/>
    <member type="way" ref="11" role="outer"/>
    <tag k="type" v="multipolygon"/>
    <tag k="leisure" v="park"/>
  </relation>
</osm>
"""
        with tempfile.NamedTemporaryFile("w", suffix=".osm") as handle:
            handle.write(osm)
            handle.flush()
            parks = fl.load_park_polygons(Path(handle.name))
        self.assertEqual(len(parks), 1)
        self.assertTrue(fl.point_in_parks(1.0, 1.0, parks))
        self.assertFalse(fl.point_in_parks(3.0, 3.0, parks))

    def test_palette_format(self) -> None:
        self.assertEqual(len(fl.KML_COLOR_PALETTE), 100)
        self.assertEqual(len(set(fl.KML_COLOR_PALETTE)), 100)
        self.assertTrue(all(len(c) == 8 and c.startswith("ff") for c in fl.KML_COLOR_PALETTE))


if __name__ == "__main__":
    unittest.main()
