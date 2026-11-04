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

MAX_LOOPS = 10
MAX_OVERLAP = 0.5
TURN_ANGLE_DEG = 30.0
SHARP_TURN_DEG = 60.0
MIN_TURN_GAP_M = 15.0

# Smallest width that still returns every cycle on the 4×4 test grid.
BEAM_WIDTH = 24
BAND_M = 40.0
PARK_NODE_FRACTION = 0.5

FOOTPATH_HIGHWAYS = {"footway", "path", "pedestrian", "steps"}
ROAD_HIGHWAYS = frozenset(
    {
        "motorway",
        "trunk",
        "primary",
        "secondary",
        "tertiary",
        "unclassified",
        "residential",
        "living_street",
        "service",
        "road",
        "motorway_link",
        "trunk_link",
        "primary_link",
        "secondary_link",
        "tertiary_link",
    }
)
ROAD_OFFSET_M = 1.0
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
    country_pbf: str,
    lat: float,
    lon: float,
    radius_m: float,
    footpaths_osm: Path,
    parks_osm: Path,
    roads_osm: Path,
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
    subprocess.run(
        [
            "osmium",
            "tags-filter",
            "--no-progress",
            "--overwrite",
            str(clipped),
            "w/highway=" + ",".join(sorted(ROAD_HIGHWAYS)),
            "-o",
            str(roads_osm),
        ],
        check=True,
    )
    clipped.unlink()


@dataclass(frozen=True)
class RoadSeg:
    lat1: float
    lon1: float
    lat2: float
    lon2: float
    grade: int


@dataclass(frozen=True)
class RoadArm:
    """The other end of a vehicle-road segment that touches a node."""

    lat: float
    lon: float
    grade: int


def way_grade(tags: dict[str, str]) -> int:
    if "layer" in tags:
        try:
            return int(float(tags["layer"]))
        except ValueError:
            return 0
    if tags.get("bridge") in {"yes", "viaduct", "boardwalk"}:
        return 1
    if tags.get("tunnel") in {"yes", "building_passage", "culvert"}:
        return -1
    return 0


def is_crossing_way(tags: dict[str, str]) -> bool:
    if tags.get("footway") in {"crossing", "traffic_island"}:
        return True
    crossing = tags.get("crossing")
    return crossing is not None and crossing != "no"


def _orient(ax: float, ay: float, bx: float, by: float, cx: float, cy: float) -> float:
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)


def segments_cross(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
    d: tuple[float, float],
) -> bool:
    """True when the open segments ab and cd intersect. A shared endpoint does not count."""
    o1 = _orient(*a, *b, *c)
    o2 = _orient(*a, *b, *d)
    o3 = _orient(*c, *d, *a)
    o4 = _orient(*c, *d, *b)
    return o1 * o2 < 0 and o3 * o4 < 0


def _on_segment_interior(
    a: tuple[float, float], b: tuple[float, float], p: tuple[float, float]
) -> bool:
    if p in (a, b) or abs(_orient(*a, *b, *p)) > 1e-12:
        return False
    return min(a[0], b[0]) <= p[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= p[1] <= max(
        a[1], b[1]
    )


def segment_crosses_road(
    lat1: float, lon1: float, lat2: float, lon2: float, grade: int, roads: Sequence[RoadSeg]
) -> bool:
    if not roads:
        return False
    a = (lon1, lat1)
    b = (lon2, lat2)
    for road in roads:
        if road.grade != grade:
            continue
        c = (road.lon1, road.lat1)
        d = (road.lon2, road.lat2)
        if (
            segments_cross(a, b, c, d)
            or _on_segment_interior(c, d, a)
            or _on_segment_interior(c, d, b)
        ):
            return True
    return False


def load_road_network(osm_xml_path: Path) -> tuple[list[RoadSeg], dict[int, tuple[RoadArm, ...]]]:
    root = DET.parse(osm_xml_path).getroot()
    nodes = {
        int(node.get("id")): (float(node.get("lat")), float(node.get("lon")))
        for node in root.iter("node")
    }
    segments: list[RoadSeg] = []
    arms: dict[int, list[RoadArm]] = defaultdict(list)
    for way in root.iter("way"):
        tags = {tag.get("k"): tag.get("v") for tag in way.iter("tag")}
        if tags.get("highway") not in ROAD_HIGHWAYS:
            continue
        grade = way_grade(tags)
        refs = [int(nd.get("ref")) for nd in way.iter("nd")]
        for u, v in zip(refs, refs[1:], strict=False):
            if u not in nodes or v not in nodes or u == v:
                continue
            lat_u, lon_u = nodes[u]
            lat_v, lon_v = nodes[v]
            segments.append(RoadSeg(lat_u, lon_u, lat_v, lon_v, grade))
            arms[u].append(RoadArm(lat_v, lon_v, grade))
            arms[v].append(RoadArm(lat_u, lon_u, grade))
    return segments, {node: tuple(node_arms) for node, node_arms in arms.items()}


def load_footpath_graph(
    osm_xml_path: Path,
    lat: float,
    lon: float,
    radius_m: float,
    road_segments: Sequence[RoadSeg] = (),
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
    skipped_crossings = 0
    for way in root.iter("way"):
        tags = {t.get("k"): t.get("v") for t in way.iter("tag")}
        hw = tags.get("highway")
        if hw not in FOOTPATH_HIGHWAYS:
            continue
        way_id = int(way.get("id"))
        grade = way_grade(tags)
        crossing_way = is_crossing_way(tags)
        refs = [int(nd.get("ref")) for nd in way.iter("nd")]
        for u, v in zip(refs, refs[1:], strict=False):
            if u not in nodes or v not in nodes:
                skipped_segments += 1
                continue
            lat_u, lon_u = nodes[u]
            lat_v, lon_v = nodes[v]
            if crossing_way or segment_crosses_road(
                lat_u, lon_u, lat_v, lon_v, grade, road_segments
            ):
                skipped_crossings += 1
                continue
            length_m = haversine_m(lat_u, lon_u, lat_v, lon_v)
            G.add_edge(u, v, osmid=way_id, highway=hw, length=length_m, grade=grade)
            added_segments += 1

    G.remove_nodes_from(list(nx.isolates(G)))

    print(f"Loaded nodes: {G.number_of_nodes()}")
    print(f"Added segments: {added_segments}")
    print(f"Skipped segments (missing endpoint node): {skipped_segments}")
    print(f"Skipped segments (cross a road): {skipped_crossings}")
    return G


def to_simple_undirected(G: nx.MultiDiGraph) -> nx.Graph:
    H = nx.Graph()
    H.add_nodes_from(G.nodes(data=True))
    for u, v, data in G.edges(data=True):
        if u == v:
            continue
        length = data["length"]
        grade = data.get("grade", 0)
        if H.has_edge(u, v):
            if length < H[u][v]["length"]:
                H[u][v]["length"] = length
                H[u][v]["grade"] = grade
        else:
            H.add_edge(u, v, length=length, grade=grade)
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


def _leg_m(lat1: float, lon1: float, lat2: float, lon2: float) -> tuple[float, float]:
    mid = math.radians((lat1 + lat2) / 2.0)
    north = math.radians(lat2 - lat1) * EARTH_RADIUS_M
    east = math.radians(lon2 - lon1) * EARTH_RADIUS_M * math.cos(mid)
    return east, north


def _heading_change_deg(
    lat0: float, lon0: float, lat1: float, lon1: float, lat2: float, lon2: float
) -> float | None:
    east_in, north_in = _leg_m(lat0, lon0, lat1, lon1)
    east_out, north_out = _leg_m(lat1, lon1, lat2, lon2)
    if east_in * east_in + north_in * north_in < 1.0:
        return None
    if east_out * east_out + north_out * north_out < 1.0:
        return None
    dot = east_in * east_out + north_in * north_out
    cross = east_in * north_out - north_in * east_out
    return math.degrees(math.atan2(cross, dot))


def turn_count(H: nx.Graph, loop: Sequence[int]) -> int:
    """Corners a runner takes. A heading change under TURN_ANGLE_DEG is not a turn."""
    coords = [(H.nodes[node]["y"], H.nodes[node]["x"]) for node in loop[:-1]]
    if len(coords) < 3:
        return 0
    turns = 0
    count = len(coords)
    for i in range(count):
        lat0, lon0 = coords[(i - 1) % count]
        lat1, lon1 = coords[i]
        lat2, lon2 = coords[(i + 1) % count]
        change = _heading_change_deg(lat0, lon0, lat1, lon1, lat2, lon2)
        if change is not None and abs(change) >= TURN_ANGLE_DEG:
            turns += 1
    return turns


def sharp_turns_clustered(H: nx.Graph, loop: Sequence[int]) -> bool:
    """True when two corners of SHARP_TURN_DEG or more lie under MIN_TURN_GAP_M apart.

    The gap is measured along the path, including across the point where the loop closes.
    """
    coords = [(H.nodes[node]["y"], H.nodes[node]["x"]) for node in loop[:-1]]
    count = len(coords)
    if count < 3:
        return False
    along: list[float] = []
    travelled = 0.0
    for i in range(count):
        lat1, lon1 = coords[i]
        lat0, lon0 = coords[(i - 1) % count]
        lat2, lon2 = coords[(i + 1) % count]
        change = _heading_change_deg(lat0, lon0, lat1, lon1, lat2, lon2)
        if change is not None and abs(change) >= SHARP_TURN_DEG:
            along.append(travelled)
        travelled += haversine_m(lat1, lon1, lat2, lon2)
    if len(along) < 2:
        return False
    gaps = [b - a for a, b in zip(along, along[1:], strict=False)]
    gaps.append(travelled - along[-1] + along[0])
    return min(gaps) < MIN_TURN_GAP_M


def loop_crosses_road(
    H: nx.Graph, loop: Sequence[int], road_arms: dict[int, tuple[RoadArm, ...]]
) -> bool:
    """True when the walk steps from one side of a vehicle road to the other.

    A crossing mapped through the road's own node does not intersect the road segment,
    so the two neighbours of that node are checked instead.
    """
    if not road_arms:
        return False
    body = loop[:-1]
    count = len(body)
    for i, node in enumerate(body):
        arms = road_arms.get(node)
        if not arms:
            continue
        prev = body[(i - 1) % count]
        nxt = body[(i + 1) % count]
        if H[prev][node].get("grade", 0) != H[node][nxt].get("grade", 0):
            continue
        grade = H[prev][node].get("grade", 0)
        nlat, nlon = H.nodes[node]["y"], H.nodes[node]["x"]
        prev_east, prev_north = _leg_m(nlat, nlon, H.nodes[prev]["y"], H.nodes[prev]["x"])
        next_east, next_north = _leg_m(nlat, nlon, H.nodes[nxt]["y"], H.nodes[nxt]["x"])
        for arm in arms:
            if arm.grade != grade:
                continue
            road_east, road_north = _leg_m(nlat, nlon, arm.lat, arm.lon)
            road_len = math.hypot(road_east, road_north)
            if road_len < 1.0:
                continue
            prev_side = (road_east * prev_north - road_north * prev_east) / road_len
            next_side = (road_east * next_north - road_north * next_east) / road_len
            opposite = prev_side * next_side < 0
            clear = abs(prev_side) >= ROAD_OFFSET_M and abs(next_side) >= ROAD_OFFSET_M
            if opposite and clear:
                return True
    return False


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
    road_arms: dict[int, tuple[RoadArm, ...]] | None = None,
    verbose: bool = False,
) -> list[tuple[list[int], float]]:
    """Return up to max_loops distinct cycles within target_m ± epsilon_m.

    The graph is reduced to junctions joined by chains. Cycles are grown from the lowest
    junction with a bounded beam. A loop that crosses a vehicle road is dropped, and so
    is one whose sharp corners sit a few metres apart. Fewer turns come first, then park
    loops, then closer lengths. A loop is skipped when more than max_overlap of its
    length is shared with a loop already kept.
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
    arms = road_arms or {}
    ranked: list[tuple[int, int, float, float, tuple[tuple[int, int], ...], list[int]]] = []
    crossed = 0
    clustered = 0
    for length, steps in found.values():
        nodes = expand(chains, steps)
        if arms and loop_crosses_road(H, nodes, arms):
            crossed += 1
            continue
        if sharp_turns_clustered(H, nodes):
            clustered += 1
            continue
        park_rank = 0 if loop_in_park(H, nodes, park_areas) else 1
        ranked.append(
            (turn_count(H, nodes), park_rank, abs(length - target_m), length, steps, nodes)
        )
    if verbose:
        print(f"Loops dropped (cross a road): {crossed}")
        print(f"Loops dropped (sharp turns within {MIN_TURN_GAP_M:.0f} m): {clustered}")
    ranked.sort(key=lambda item: (item[0], item[1], item[2], item[3]))

    kept: list[tuple[list[int], float]] = []
    kept_by_chain: dict[int, list[int]] = defaultdict(list)
    for _, _, _, total, steps, nodes in ranked:
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
        turns = turn_count(H, loop)
        SubElement(pm, "name").text = f"Loop {i + 1}: {length:.0f} m, {turns} turns"
        SubElement(
            pm, "description"
        ).text = (
            f"{length:.1f} m, {turns} turns, {len(loop) - 1} nodes, Δ {length - target_m:+.1f} m"
        )
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
    roads_osm = out_dir / "roads.osm"
    kml_path = out_dir / "loops.kml"

    extract_osm(args.pbf, lat, lon, args.radius, footpaths_osm, parks_osm, roads_osm)
    road_segments, road_arms = load_road_network(roads_osm)
    G = load_footpath_graph(footpaths_osm, lat, lon, args.radius, road_segments)
    H = to_simple_undirected(G)
    if USE_K_CORE and not args.no_k_core:
        H = prune_k_core(H, K_CORE_K)
    parks = load_park_polygons(parks_osm)
    print(f"Park polygons: {len(parks)}")

    loops = find_loops(
        H,
        args.target,
        args.epsilon,
        args.max_loops,
        args.max_overlap,
        parks,
        road_arms,
        verbose=True,
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
