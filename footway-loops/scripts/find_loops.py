"""Find closed footpath loops within a radius of a point; export KML + one GPX per loop."""

import argparse
import colorsys
import math
import subprocess
from collections.abc import Iterable
from pathlib import Path
from xml.etree.ElementTree import Element, ElementTree, SubElement  # noqa: S405

import defusedxml.ElementTree as DET
import networkx as nx

COUNTRY_PBF = "data/vietnam-latest.osm.pbf"
CENTER_LAT = 20.9947
CENTER_LON = 105.8679
RADIUS_M = 700.0
OUT_DIR = "data"

TARGET_LENGTH_M = 883.0
EPSILON_M = 50.0

MAX_DEPTH = 100
MAX_LOOPS = 500

FOOTPATH_HIGHWAYS = {"footway", "path", "pedestrian", "steps"}

USE_K_CORE = True
K_CORE_K = 2

EARTH_RADIUS_M = 6_371_008.8
GOLDEN_ANGLE_DEG = 137.50776405003785


def generate_kml_color_palette(n: int) -> list[str]:
    saturations = (0.95, 0.65)
    values = (0.95, 0.70)
    palette = []
    for i in range(n):
        hue = (i * GOLDEN_ANGLE_DEG) % 360.0 / 360.0
        s = saturations[i % 2]
        v = values[(i // 2) % 2]
        r, g, b = colorsys.hsv_to_rgb(hue, s, v)
        palette.append(f"ff{round(b * 255):02x}{round(g * 255):02x}{round(r * 255):02x}")
    return palette


KML_COLOR_PALETTE = generate_kml_color_palette(100)


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def extract_footpaths(
    country_pbf: str, lat: float, lon: float, radius_m: float, out_osm: Path
) -> None:
    dlat = math.degrees(radius_m / EARTH_RADIUS_M)
    dlon = dlat / math.cos(math.radians(lat))
    bbox = f"{lon - dlon},{lat - dlat},{lon + dlon},{lat + dlat}"
    clipped = out_osm.with_suffix(".pbf")
    subprocess.run(
        ["osmium", "extract", "--overwrite", "-b", bbox, country_pbf, "-o", str(clipped)],
        check=True,
    )
    highways = ",".join(sorted(FOOTPATH_HIGHWAYS))
    subprocess.run(
        [
            "osmium",
            "tags-filter",
            "--overwrite",
            str(clipped),
            f"w/highway={highways}",
            "-o",
            str(out_osm),
        ],
        check=True,
    )
    clipped.unlink()


def load_footpath_graph(
    osm_xml_path: Path, lat: float, lon: float, radius_m: float
) -> nx.MultiDiGraph:
    """Nodes outside the circle are dropped, so segments that leave it count as skipped."""
    root = DET.parse(osm_xml_path).getroot()

    nodes: dict[int, tuple[float, float]] = {}
    for n in root.iter("node"):
        node_lat, node_lon = float(n.get("lat")), float(n.get("lon"))
        if haversine_m(lat, lon, node_lat, node_lon) <= radius_m:
            nodes[int(n.get("id"))] = (node_lat, node_lon)

    G = nx.MultiDiGraph()
    for node_id, (lat, lon) in nodes.items():
        G.add_node(node_id, y=lat, x=lon)

    added_segments = 0
    skipped_segments = 0
    for way in root.iter("way"):
        tags = {t.get("k"): t.get("v") for t in way.iter("tag")}
        hw = tags.get("highway")
        if hw not in FOOTPATH_HIGHWAYS:
            continue
        way_id = int(way.get("id"))
        refs = [int(nd.get("ref")) for nd in way.iter("nd")]
        for u, v in zip(refs, refs[1:], strict=False):
            if u not in nodes or v not in nodes:
                skipped_segments += 1
                continue
            length_m = haversine_m(*nodes[u], *nodes[v])
            G.add_edge(u, v, osmid=way_id, highway=hw, length=length_m)
            added_segments += 1

    G.remove_nodes_from(list(nx.isolates(G)))

    print(f"Loaded nodes: {G.number_of_nodes()}")
    print(f"Added segments: {added_segments}")
    print(f"Skipped segments (missing endpoint node): {skipped_segments}")
    return G


def to_simple_undirected(G: nx.MultiDiGraph) -> nx.Graph:
    H = nx.Graph()
    H.add_nodes_from(G.nodes(data=True))
    for u, v, data in G.edges(data=True):
        if u == v:
            continue
        length = data["length"]
        if H.has_edge(u, v):
            if length < H[u][v]["length"]:
                H[u][v]["length"] = length
        else:
            H.add_edge(u, v, length=length)
    H.remove_nodes_from(list(nx.isolates(H)))
    return H


def prune_k_core(H: nx.Graph, k: int) -> nx.Graph:
    print(f"Before k-core: {H.number_of_nodes()} nodes, {H.number_of_edges()} edges")
    core = nx.k_core(H, k=k).copy()
    core.remove_nodes_from(list(nx.isolates(core)))
    print(f"After {k}-core: {core.number_of_nodes()} nodes, {core.number_of_edges()} edges")
    return core


def canonical_cycle(cycle: list[int]) -> tuple[int, ...]:
    i = cycle.index(min(cycle))
    rotated = cycle[i:] + cycle[:i]
    reversed_ = [rotated[0], *reversed(rotated[1:])]
    return tuple(min(rotated, reversed_))


def find_loops(
    H: nx.Graph,
    target_m: float,
    epsilon_m: float,
    max_depth: int,
    max_loops: int,
) -> list[tuple[list[int], float]]:
    """Return simple cycles whose length is within target_m ± epsilon_m.

    Each cycle is found from its smallest node only (neighbours below `start` are skipped);
    a branch is cut once its length plus the straight-line distance home exceeds the upper bound.
    """
    lo, hi = target_m - epsilon_m, target_m + epsilon_m
    coords = {n: (d["y"], d["x"]) for n, d in H.nodes(data=True)}
    seen: set[tuple[int, ...]] = set()
    loops: list[tuple[list[int], float]] = []

    for start in sorted(H.nodes):
        start_lat, start_lon = coords[start]
        path = [start]
        on_path = {start}
        lengths = [0.0]
        stack = [iter(sorted(H[start]))]

        while stack:
            u = path[-1]
            v = next(stack[-1], None)
            if v is None:
                stack.pop()
                on_path.discard(path.pop())
                lengths.pop()
                continue
            if v < start:
                continue

            total = lengths[-1] + H[u][v]["length"]

            if v == start:
                if len(path) >= 3 and lo <= total <= hi:
                    key = canonical_cycle(path)
                    if key not in seen:
                        seen.add(key)
                        loops.append(([*path, start], total))
                        if len(loops) >= max_loops:
                            return loops
                continue

            if v in on_path or len(path) >= max_depth:
                continue
            if total + haversine_m(*coords[v], start_lat, start_lon) > hi:
                continue

            path.append(v)
            on_path.add(v)
            lengths.append(total)
            stack.append(iter(sorted(H[v])))

    return loops


def loop_coords(H: nx.Graph, loop: Iterable[int]) -> list[tuple[float, float]]:
    return [(H.nodes[n]["y"], H.nodes[n]["x"]) for n in loop]


def write_kml(
    H: nx.Graph, loops: list[tuple[list[int], float]], target_m: float, path: str
) -> None:
    kml = Element("kml", xmlns="http://www.opengis.net/kml/2.2")
    doc = SubElement(kml, "Document")
    SubElement(doc, "name").text = Path(path).stem

    for i, (loop, length) in enumerate(loops):
        style_id = f"loop{i}"
        style = SubElement(doc, "Style", id=style_id)
        line = SubElement(style, "LineStyle")
        SubElement(line, "color").text = KML_COLOR_PALETTE[i % len(KML_COLOR_PALETTE)]
        SubElement(line, "width").text = "4"

        pm = SubElement(doc, "Placemark")
        SubElement(pm, "name").text = f"Loop {i + 1}: {length:.0f} m"
        SubElement(
            pm, "description"
        ).text = f"{length:.1f} m, {len(loop) - 1} nodes, Δ {length - target_m:+.1f} m"
        SubElement(pm, "styleUrl").text = f"#{style_id}"
        ls = SubElement(pm, "LineString")
        SubElement(ls, "tessellate").text = "1"
        SubElement(ls, "coordinates").text = " ".join(
            f"{lon:.7f},{lat:.7f},0" for lat, lon in loop_coords(H, loop)
        )

    tree = ElementTree(kml)
    tree.write(path, encoding="utf-8", xml_declaration=True)


def write_gpx(H: nx.Graph, loop: list[int], length: float, name: str, path: Path) -> None:
    gpx = Element(
        "gpx",
        version="1.1",
        creator="footway-loops",
        xmlns="http://www.topografix.com/GPX/1/1",
    )
    trk = SubElement(gpx, "trk")
    SubElement(trk, "name").text = name
    SubElement(trk, "desc").text = f"{length:.1f} m"
    seg = SubElement(trk, "trkseg")
    for lat, lon in loop_coords(H, loop):
        SubElement(seg, "trkpt", lat=f"{lat:.7f}", lon=f"{lon:.7f}")
    ElementTree(gpx).write(path, encoding="utf-8", xml_declaration=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pbf", default=COUNTRY_PBF, help="country .osm.pbf to clip from")
    parser.add_argument("--lat", type=float, default=CENTER_LAT)
    parser.add_argument("--lon", type=float, default=CENTER_LON)
    parser.add_argument("--radius", type=float, default=RADIUS_M, help="metres")
    parser.add_argument("--target", type=float, default=TARGET_LENGTH_M, help="metres")
    parser.add_argument("--epsilon", type=float, default=EPSILON_M, help="metres")
    parser.add_argument("--max-depth", type=int, default=MAX_DEPTH)
    parser.add_argument("--max-loops", type=int, default=MAX_LOOPS)
    parser.add_argument("--out-dir", default=OUT_DIR)
    parser.add_argument("--no-k-core", action="store_true")
    args = parser.parse_args()

    out_dir = Path(args.out_dir) / f"{args.lat:.5f}_{args.lon:.5f}_{args.radius:.0f}m"
    gpx_dir = out_dir / "gpx"
    gpx_dir.mkdir(parents=True, exist_ok=True)
    footpaths_osm = out_dir / "footpaths.osm"
    kml_path = out_dir / "loops.kml"

    extract_footpaths(args.pbf, args.lat, args.lon, args.radius, footpaths_osm)
    G = load_footpath_graph(footpaths_osm, args.lat, args.lon, args.radius)
    H = to_simple_undirected(G)
    if USE_K_CORE and not args.no_k_core:
        H = prune_k_core(H, K_CORE_K)

    loops = find_loops(H, args.target, args.epsilon, args.max_depth, args.max_loops)
    loops.sort(key=lambda item: abs(item[1] - args.target))
    print(f"Found loops: {len(loops)}")

    write_kml(H, loops, args.target, str(kml_path))
    print(f"Wrote {kml_path}")

    for old in gpx_dir.glob("loop_*.gpx"):
        old.unlink()
    for i, (loop, length) in enumerate(loops, start=1):
        name = f"loop_{i:03d}_{length:.0f}m"
        write_gpx(H, loop, length, name, gpx_dir / f"{name}.gpx")
    print(f"Wrote {len(loops)} GPX files to {gpx_dir}")


if __name__ == "__main__":
    main()
