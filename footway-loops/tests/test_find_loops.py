import sys
import unittest
from pathlib import Path

import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import find_loops as fl


def grid(n: int, step_m: float) -> nx.Graph:
    H = nx.grid_2d_graph(n, n)
    H = nx.convert_node_labels_to_integers(H, label_attribute="rc")
    deg = step_m / 111_195.0
    for _, data in H.nodes(data=True):
        r, c = data["rc"]
        data["y"], data["x"] = r * deg, c * deg
    for u, v in H.edges:
        H[u][v]["length"] = step_m
    return H


class FindLoopsTest(unittest.TestCase):
    def test_unit_squares_found_once_each(self) -> None:
        loops = fl.find_loops(grid(3, 100.0), 400.0, 1.0, 100, 500)
        self.assertEqual(len(loops), 4)
        for loop, length in loops:
            self.assertEqual(loop[0], loop[-1])
            self.assertEqual(len(set(loop[:-1])), 4)
            self.assertAlmostEqual(length, 400.0)

    def test_length_window(self) -> None:
        loops = fl.find_loops(grid(3, 100.0), 600.0, 1.0, 100, 500)
        self.assertEqual(len(loops), 4)
        self.assertTrue(all(abs(length - 600.0) < 1.0 for _, length in loops))

    def test_max_loops_cap(self) -> None:
        self.assertEqual(len(fl.find_loops(grid(4, 100.0), 400.0, 1.0, 100, 3)), 3)

    def test_palette_format(self) -> None:
        self.assertEqual(len(fl.KML_COLOR_PALETTE), 100)
        self.assertEqual(len(set(fl.KML_COLOR_PALETTE)), 100)
        self.assertTrue(all(len(c) == 8 and c.startswith("ff") for c in fl.KML_COLOR_PALETTE))


if __name__ == "__main__":
    unittest.main()
