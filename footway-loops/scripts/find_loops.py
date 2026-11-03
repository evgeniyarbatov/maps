"""Find closed footpath loops within a radius of a point; export KML + one GPX per loop."""

import argparse
import colorsys
import math
import subprocess
from collections import defaultdict, deque
from collections.abc import Iterable, Sequence
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

# Smallest width that still returns every cycle on the 4×4 test grid.
BEAM_WIDTH = 24
BAND_M = 40.0
PARK_NODE_FRACTION = 0.5

FOOTPATH_HIGHWAYS = {"footway", "path", "pedestrian", "steps"}
PARK_FILTERS = (
    "w/leisure=park,garden",
    "w/landuse=recreation_ground",
    "r/leisure=park,garden",
    "r/landuse=recreation_ground",
)

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


def extract_osm(
    country_pbf: str, lat: float, lon: float, radius_m: float, footpaths_osm: Path, parks_osm: Path
) -> None:
    dlat = math.degrees(radius_m / EARTH_RADIUS_M)
    dlon = dlat / math.cos(math.radians(lat))
    bbox = f"{lon - dlon},{lat - dlat},{lon + dlon},{lat + dlat}"
    clipped = footpaths_osm.with_suffix(".pbf")
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
            str(footpaths_osm),
        ],
        check=True,
    )
    subprocess.run(
        [
            "osmium",
            "tags-filter",
            "--no-progress",
            "--overwrite",
            str(clipped),
            *PARK_FILTERS,
            "-o",
            str(parks_osm),
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


@dataclass(frozen=True)
class Park:
    """Outer rings and holes as closed `(lat, lon)` loops."""

    outers: tuple[tuple[tuple[float, float], ...], ...]
    inners: tuple[tuple[tuple[float, float], ...], ...] = ()


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


def beam_cycles(
    adj: dict[int, list[tuple[int, int]]],
    chains: list[Chain],
    junction_count: int,
    lo: float,
    hi: float,
) -> dict[int, tuple[float, tuple[tuple[int, int], ...]]]:
    """Simple cycles in `[lo, hi]`, one per chain set, grown from the lowest junction.

    Each junction keeps at most `BEAM_WIDTH` partial paths in a length band. Further
    arrivals in that band are not extended.
    """
    found: dict[int, tuple[float, tuple[tuple[int, int], ...]]] = {}
    for start in range(junction_count):
        kept: dict[tuple[int, int], int] = {(start, 0): 1}
        queue: deque[HalfPath] = deque([HalfPath(start, 0.0, 1 << start, 0, ())])
        while queue:
            path = queue.popleft()
            for cid, end in adj[path.end]:
                if path.chains >> cid & 1:
                    continue
                length = path.length + chains[cid].length
                if length > hi:
                    continue
                if end == start:
                    if length >= lo:
                        mask = path.chains | 1 << cid
                        found.setdefault(mask, (length, (*path.steps, (cid, path.end))))
                    continue
                if end < start or path.junctions >> end & 1:
                    continue
                band = int(length // BAND_M)
                slot = (end, band)
                if kept.get(slot, 0) >= BEAM_WIDTH:
                    continue
                kept[slot] = kept.get(slot, 0) + 1
                queue.append(
                    HalfPath(
                        end,
                        length,
                        path.junctions | 1 << end,
                        path.chains | 1 << cid,
                        (*path.steps, (cid, path.end)),
                    )
                )
    return found


def expand(chains: list[Chain], steps: Iterable[tuple[int, int]]) -> list[int]:
    nodes: list[int] = []
    for cid, frm in steps:
        chain = chains[cid].nodes
        seq = chain if chains[cid].a == frm else chain[::-1]
        nodes.extend(seq if not nodes else seq[1:])
    return nodes


def point_in_ring(lat: float, lon: float, ring: Sequence[tuple[float, float]]) -> bool:
    inside = False
    for (lat1, lon1), (lat2, lon2) in zip(ring, ring[1:], strict=False):
        if (lat1 > lat) == (lat2 > lat):
            continue
        lon_at = lon1 + (lon2 - lon1) * (lat - lat1) / (lat2 - lat1)
        if lon < lon_at:
            inside = not inside
    return inside


def point_in_parks(lat: float, lon: float, parks: Sequence[Park]) -> bool:
    for park in parks:
        if any(point_in_ring(lat, lon, ring) for ring in park.outers) and not any(
            point_in_ring(lat, lon, ring) for ring in park.inners
        ):
            return True
    return False


def _is_park(tags: dict[str, str]) -> bool:
    return tags.get("leisure") in {"park", "garden"} or tags.get("landuse") == "recreation_ground"


def _link_ring(ring: list[int], part: list[int]) -> list[int] | None:
    if part[0] == ring[-1]:
        return ring + part[1:]
    if part[-1] == ring[-1]:
        return ring + part[-2::-1]
    if part[-1] == ring[0]:
        return part[:-1] + ring
    if part[0] == ring[0]:
        return part[:0:-1] + ring
    return None


def _stitch_rings(parts: list[list[int]]) -> list[list[int]]:
    """Join way fragments that share an endpoint. Multipolygon rings are often split."""
    unused = [list(part) for part in parts if len(part) >= 2]
    rings: list[list[int]] = []
    while unused:
        ring = unused.pop()
        if ring[0] != ring[-1]:
            progressed = True
            while progressed and ring[0] != ring[-1]:
                progressed = False
                for i, part in enumerate(unused):
                    linked = _link_ring(ring, part)
                    if linked is None:
                        continue
                    ring = linked
                    del unused[i]
                    progressed = True
                    break
        if ring[0] == ring[-1] and len(ring) >= 4:
            rings.append(ring)
    return rings


def _ring_coords(
    node_ids: list[int], nodes: dict[int, tuple[float, float]]
) -> tuple[tuple[float, float], ...] | None:
    coords: list[tuple[float, float]] = []
    for node_id in node_ids:
        point = nodes.get(node_id)
        if point is None:
            return None
        coords.append(point)
    return tuple(coords)


def load_park_polygons(osm_xml_path: Path) -> list[Park]:
    root = DET.parse(osm_xml_path).getroot()
    nodes = {
        int(node.get("id")): (float(node.get("lat")), float(node.get("lon")))
        for node in root.iter("node")
    }
    ways = {
        int(way.get("id")): [int(nd.get("ref")) for nd in way.iter("nd")]
        for way in root.iter("way")
    }
    way_tags = {
        int(way.get("id")): {tag.get("k"): tag.get("v") for tag in way.iter("tag")}
        for way in root.iter("way")
    }
    parks: list[Park] = []
    for way_id, tags in way_tags.items():
        refs = ways[way_id]
        if not _is_park(tags) or len(refs) < 4 or refs[0] != refs[-1]:
            continue
        ring = _ring_coords(refs, nodes)
        if ring is not None:
            parks.append(Park(outers=(ring,)))

    for rel in root.iter("relation"):
        tags = {tag.get("k"): tag.get("v") for tag in rel.iter("tag")}
        if not _is_park(tags):
            continue
        grouped: dict[str, list[list[int]]] = {"outer": [], "inner": []}
        for member in rel.iter("member"):
            if member.get("type") != "way":
                continue
            role = member.get("role") or "outer"
            if role not in grouped:
                continue
            refs = ways.get(int(member.get("ref")))
            if refs:
                grouped[role].append(refs)
        outers = [
            coords
            for ring in _stitch_rings(grouped["outer"])
            if (coords := _ring_coords(ring, nodes)) is not None
        ]
        inners = [
            coords
            for ring in _stitch_rings(grouped["inner"])
            if (coords := _ring_coords(ring, nodes)) is not None
        ]
        if outers:
            parks.append(Park(outers=tuple(outers), inners=tuple(inners)))
    return parks


def loop_in_park(H: nx.Graph, loop: Sequence[int], parks: Sequence[Park]) -> bool:
    body = loop[:-1]
    if not parks or not body:
        return False
    inside = sum(
        1 for node in body if point_in_parks(H.nodes[node]["y"], H.nodes[node]["x"], parks)
    )
    return inside >= PARK_NODE_FRACTION * len(body)


def find_loops(
    H: nx.Graph,
    target_m: float,
    epsilon_m: float,
    max_loops: int,
    max_overlap: float,
    parks: Sequence[Park] | None = None,
    verbose: bool = False,
) -> list[tuple[list[int], float]]:
    """Return up to max_loops distinct cycles within target_m ± epsilon_m.

    The graph is reduced to junctions joined by chains. Cycles are grown from the lowest
    junction with a bounded beam. Park loops come first, then closer lengths. A loop is
    skipped when more than max_overlap of its length is shared with a loop already kept.
    """
    lo, hi = target_m - epsilon_m, target_m + epsilon_m
    raw = contract_chains(H)
    if not raw:
        if verbose:
            print("Junction graph: 0 junctions, 0 chains")
        return []
    index = {j: i for i, j in enumerate(sorted({c.a for c in raw} | {c.b for c in raw}))}
    chains = [Chain(index[c.a], index[c.b], c.length, c.nodes) for c in raw]
    adj: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for cid, chain in enumerate(chains):
        adj[chain.a].append((cid, chain.b))
        if chain.a != chain.b:
            adj[chain.b].append((cid, chain.a))

    if verbose:
        print(f"Junction graph: {len(index)} junctions, {len(chains)} chains")
    found = beam_cycles(adj, chains, len(index), lo, hi)
    if verbose:
        print(f"Cycle candidates: {len(found)}")

    park_areas = parks or ()
    ranked: list[tuple[int, float, float, tuple[tuple[int, int], ...], list[int]]] = []
    for length, steps in found.values():
        nodes = expand(chains, steps)
        park_rank = 0 if loop_in_park(H, nodes, park_areas) else 1
        ranked.append((park_rank, abs(length - target_m), length, steps, nodes))
    ranked.sort(key=lambda item: (item[0], item[1], item[2]))

    kept: list[tuple[list[int], float]] = []
    kept_by_chain: dict[int, list[int]] = defaultdict(list)
    for _, _, total, steps, nodes in ranked:
        shared: dict[int, float] = defaultdict(float)
        for cid, _ in steps:
            for kept_index in kept_by_chain[cid]:
                shared[kept_index] += chains[cid].length
        if shared and max(shared.values()) > max_overlap * total:
            continue
        for cid, _ in steps:
            kept_by_chain[cid].append(len(kept))
        kept.append((nodes, total))
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
    parks_osm = out_dir / "parks.osm"
    kml_path = out_dir / "loops.kml"

    extract_osm(args.pbf, lat, lon, args.radius, footpaths_osm, parks_osm)
    G = load_footpath_graph(footpaths_osm, lat, lon, args.radius)
    H = to_simple_undirected(G)
    if USE_K_CORE and not args.no_k_core:
        H = prune_k_core(H, K_CORE_K)
    parks = load_park_polygons(parks_osm)
    print(f"Park polygons: {len(parks)}")

    loops = find_loops(
        H, args.target, args.epsilon, args.max_loops, args.max_overlap, parks, verbose=True
    )
    in_parks = sum(loop_in_park(H, loop, parks) for loop, _ in loops)
    print(f"Found loops: {len(loops)} ({in_parks} in parks)")

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
