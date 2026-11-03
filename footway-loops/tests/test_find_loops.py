import sys
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

    def test_palette_format(self) -> None:
        self.assertEqual(len(fl.KML_COLOR_PALETTE), 100)
        self.assertEqual(len(set(fl.KML_COLOR_PALETTE)), 100)
        self.assertTrue(all(len(c) == 8 and c.startswith("ff") for c in fl.KML_COLOR_PALETTE))


if __name__ == "__main__":
    unittest.main()
