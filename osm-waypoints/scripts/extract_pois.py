#!/usr/bin/env python3
"""Extract hiking-relevant POIs from an OSM extract."""

from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from config import DATA_DIR, OSM_EXTRACT, POIS_RAW
from poi_rules import matches_poi, poi_display_name

OSM_NS = {"osm": "http://www.openstreetmap.org/osm/0.6"}


def parse_nodes(root: ET.Element) -> dict[str, tuple[float, float]]:
    nodes: dict[str, tuple[float, float]] = {}
    for node in root.findall("node"):
        node_id = node.get("id")
        lat = node.get("lat")
        lon = node.get("lon")
        if node_id and lat and lon:
            nodes[node_id] = (float(lat), float(lon))
    return nodes


def node_tags(node: ET.Element) -> dict[str, str]:
    return {tag.get("k", ""): tag.get("v", "") for tag in node.findall("tag")}


def way_centroid(way: ET.Element, nodes: dict[str, tuple[float, float]]) -> tuple[float, float] | None:
    coords: list[tuple[float, float]] = []
    for nd in way.findall("nd"):
        ref = nd.get("ref")
        if ref and ref in nodes:
            coords.append(nodes[ref])
    if not coords:
        return None
    lat = sum(c[0] for c in coords) / len(coords)
    lon = sum(c[1] for c in coords) / len(coords)
    return lat, lon


def tags_from_element(element: ET.Element) -> dict[str, str]:
    return {tag.get("k", ""): tag.get("v", "") for tag in element.findall("tag")}


def extract_pois(osm_path: Path) -> list[dict]:
    root = ET.parse(osm_path).getroot()
    nodes = parse_nodes(root)
    pois: list[dict] = []
    seen: set[str] = set()

    for node in root.findall("node"):
        tags = node_tags(node)
        category = matches_poi(tags)
        if not category:
            continue

        node_id = node.get("id", "")
        poi_id = f"node/{node_id}"
        if poi_id in seen:
            continue
        seen.add(poi_id)

        lat = float(node.get("lat", "0"))
        lon = float(node.get("lon", "0"))
        ele = node.get("ele")

        pois.append(
            {
                "id": poi_id,
                "name": poi_display_name(tags),
                "lat": lat,
                "lon": lon,
                "ele": float(ele) if ele else None,
                "category": category,
                "tags": tags,
            }
        )

    for way in root.findall("way"):
        tags = tags_from_element(way)
        category = matches_poi(tags)
        if not category:
            continue

        way_id = way.get("id", "")
        poi_id = f"way/{way_id}"
        if poi_id in seen:
            continue

        centroid = way_centroid(way, nodes)
        if centroid is None:
            continue
        seen.add(poi_id)

        lat, lon = centroid
        pois.append(
            {
                "id": poi_id,
                "name": poi_display_name(tags),
                "lat": lat,
                "lon": lon,
                "ele": None,
                "category": category,
                "tags": tags,
            }
        )

    pois.sort(key=lambda p: (p["name"].lower(), p["id"]))
    return pois


def main() -> int:
    if not OSM_EXTRACT.is_file():
        print(f"OSM extract not found: {OSM_EXTRACT}\nRun `make extract-osm` first.", file=sys.stderr)
        return 1

    pois = extract_pois(OSM_EXTRACT)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    payload = {"source": str(OSM_EXTRACT), "count": len(pois), "waypoints": pois}
    POIS_RAW.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")

    print(f"Extracted {len(pois)} POIs to {POIS_RAW}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())