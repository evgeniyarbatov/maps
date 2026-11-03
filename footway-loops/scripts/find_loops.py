"""Find closed footpath loops within a radius of a point; export KML + one GPX per loop."""

import argparse
import bisect
import colorsys
import math
import subprocess
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from xml.etree.ElementTree import Element, ElementTree, SubElement  # noqa: S405

import defusedxml.ElementTree as DET
import networkx as nx

OUT_DIR = Path.home() / "Documents/data/footway-loops"
COUNTRY_PBF = OUT_DIR / "vietnam-latest.osm.pbf"
LOCATION = "20.9947,105.8679"
RADIUS_M = 700.0

TARGET_LENGTH_M = 883.0
EPSILON_M = 50.0

MAX_LOOPS = 500
MAX_OVERLAP = 0.5

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
        [
            "osmium",
            "extract",
            "--no-progress",
            "--overwrite",
            "-b",
            bbox,
            country_pbf,
            "-o",
            str(clipped),
        ],
        check=True,
    )
    highways = ",".join(sorted(FOOTPATH_HIGHWAYS))
    subprocess.run(
        [
            "osmium",
            "tags-filter",
            "--no-progress",
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


@dataclass(frozen=True)
class Chain:
    """A run of degree-2 nodes between two junctions; `nodes` goes from `a` to `b`."""

    a: int
    b: int
    length: float
    nodes: tuple[int, ...]


@dataclass(frozen=True)
class HalfPath:
    end: int
    length: float
    junctions: int
    chains: int
    steps: tuple[tuple[int, int], ...]


def contract_chains(H: nx.Graph) -> list[Chain]:
    junctions = {n for n, d in H.degree() if d != 2}
    for component in nx.connected_components(H):
        if junctions.isdisjoint(component):
            junctions.add(min(component))

    chains = []
    walked: set[frozenset[int]] = set()
    for a in sorted(junctions):
        for first in sorted(H[a]):
            if frozenset((a, first)) in walked:
                continue
            nodes = [a, first]
            length = H[a][first]["length"]
            walked.add(frozenset((a, first)))
            while nodes[-1] not in junctions:
                prev, cur = nodes[-2], nodes[-1]
                nxt = next(n for n in H[cur] if n != prev)
                walked.add(frozenset((cur, nxt)))
                length += H[cur][nxt]["length"]
                nodes.append(nxt)
            chains.append(Chain(a, nodes[-1], length, tuple(nodes)))
    return chains


def half_paths(
    adj: dict[int, list[tuple[int, int]]], chains: list[Chain], start: int, max_len: float
) -> dict[int, list[HalfPath]]:
    """Simple junction paths from `start` up to `max_len`, through junctions above `start` only."""
    by_end: dict[int, list[HalfPath]] = defaultdict(list)
    stack = [HalfPath(start, 0.0, 1 << start, 0, ())]
    while stack:
        p = stack.pop()
        by_end[p.end].append(p)
        for cid, v in adj[p.end]:
            length = p.length + chains[cid].length
            if v <= start or p.junctions >> v & 1 or length > max_len:
                continue
            stack.append(
                HalfPath(
                    v, length, p.junctions | 1 << v, p.chains | 1 << cid, (*p.steps, (cid, p.end))
                )
            )
    for paths in by_end.values():
        paths.sort(key=lambda p: p.length)
    return by_end


def expand(chains: list[Chain], steps: Iterable[tuple[int, int]]) -> list[int]:
    nodes: list[int] = []
    for cid, frm in steps:
        chain = chains[cid].nodes
        seq = chain if chains[cid].a == frm else chain[::-1]
        nodes.extend(seq if not nodes else seq[1:])
    return nodes


def find_loops(
    H: nx.Graph,
    target_m: float,
    epsilon_m: float,
    max_loops: int,
    max_overlap: float,
) -> list[tuple[list[int], float]]:
    """Return up to max_loops distinct cycles within target_m ± epsilon_m, closest first.

    The graph is reduced to junctions joined by chains. A cycle through its lowest junction `s`
    is split at the chain holding its midpoint: two simple half-paths from `s`, each at most half
    the length, joined by that chain. A loop is skipped when more than max_overlap of its length
    is shared with a loop already kept.
    """
    lo, hi = target_m - epsilon_m, target_m + epsilon_m
    raw = contract_chains(H)
    index = {j: i for i, j in enumerate(sorted({c.a for c in raw} | {c.b for c in raw}))}
    chains = [Chain(index[c.a], index[c.b], c.length, c.nodes) for c in raw]
    adj: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for cid, c in enumerate(chains):
        adj[c.a].append((cid, c.b))
        if c.a != c.b:
            adj[c.b].append((cid, c.a))

    candidates: list[tuple[float, float, int, tuple[tuple[int, int], ...]]] = []
    for s in range(len(index)):
        by_end = half_paths(adj, chains, s, hi / 2)
        for out in (p for paths in by_end.values() for p in paths):
            for cid, v in adj[out.end]:
                if v < s or (v != s and out.junctions >> v & 1) or out.chains >> cid & 1:
                    continue
                mid = chains[cid].length
                backs = by_end.get(v, [])
                i = bisect.bisect_left(
                    backs, max(lo - out.length - mid, out.length - mid), key=lambda p: p.length
                )
                for back in backs[i:]:
                    if back.length > hi - out.length - mid or back.length >= out.length + mid:
                        break
                    if out.junctions & back.junctions != 1 << s or back.chains >> cid & 1:
                        continue
                    first_out = out.steps[0][0] if out.steps else cid
                    first_back = back.steps[0][0] if back.steps else cid
                    if first_out > first_back:
                        continue
                    total = out.length + mid + back.length
                    rev_back = tuple(
                        (c, chains[c].b if chains[c].a == f else chains[c].a)
                        for c, f in reversed(back.steps)
                    )
                    steps = (*out.steps, (cid, out.end), *rev_back)
                    candidates.append(
                        (abs(total - target_m), total, out.chains | back.chains | 1 << cid, steps)
                    )

    candidates.sort(key=lambda c: c[0])
    kept: list[tuple[list[int], float]] = []
    kept_by_chain: dict[int, list[int]] = defaultdict(list)
    for _, total, _, steps in candidates:
        shared: dict[int, float] = defaultdict(float)
        for cid, _ in steps:
            for k in kept_by_chain[cid]:
                shared[k] += chains[cid].length
        if shared and max(shared.values()) > max_overlap * total:
            continue
        for cid, _ in steps:
            kept_by_chain[cid].append(len(kept))
        kept.append((expand(chains, steps), total))
        if len(kept) >= max_loops:
            break
    return kept


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
    parser.add_argument("--location", default=LOCATION, help="lat,lon")
    parser.add_argument("--radius", type=float, default=RADIUS_M, help="metres")
    parser.add_argument("--target", type=float, default=TARGET_LENGTH_M, help="metres")
    parser.add_argument("--epsilon", type=float, default=EPSILON_M, help="metres")
    parser.add_argument("--max-loops", type=int, default=MAX_LOOPS)
    parser.add_argument(
        "--max-overlap", type=float, default=MAX_OVERLAP, help="share of a loop's length"
    )
    parser.add_argument("--out-dir", default=OUT_DIR)
    parser.add_argument("--no-k-core", action="store_true")
    args = parser.parse_args()
    lat, lon = (float(part) for part in args.location.split(","))

    out_dir = Path(args.out_dir) / f"{lat:.5f}_{lon:.5f}_{args.radius:.0f}m"
    gpx_dir = out_dir / "gpx"
    gpx_dir.mkdir(parents=True, exist_ok=True)
    footpaths_osm = out_dir / "footpaths.osm"
    kml_path = out_dir / "loops.kml"

    extract_footpaths(args.pbf, lat, lon, args.radius, footpaths_osm)
    G = load_footpath_graph(footpaths_osm, lat, lon, args.radius)
    H = to_simple_undirected(G)
    if USE_K_CORE and not args.no_k_core:
        H = prune_k_core(H, K_CORE_K)

    loops = find_loops(H, args.target, args.epsilon, args.max_loops, args.max_overlap)
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
