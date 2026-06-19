#!/usr/bin/env python3
"""Export validated waypoints to a Garmin-compatible GPX file."""

from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from xml.dom import minidom

from config import DATA_DIR, POIS_RAW, POIS_VALIDATED, WAYPOINTS_GPX
from garmin_symbols import garmin_symbol
from text_utils import to_english

GPX_NS = "http://www.topografix.com/GPX/1/1"
ET.register_namespace("", GPX_NS)


def load_waypoints() -> list[dict]:
    source = POIS_VALIDATED if POIS_VALIDATED.is_file() else POIS_RAW
    if not source.is_file():
        raise FileNotFoundError(
            f"No waypoint data found. Expected {POIS_VALIDATED} or {POIS_RAW}."
        )

    payload = json.loads(source.read_text())
    waypoints = payload.get("waypoints", [])

    if source == POIS_VALIDATED:
        return [w for w in waypoints if w.get("valid", True)]

    return waypoints


def build_gpx(waypoints: list[dict]) -> ET.Element:
    gpx = ET.Element(
        "gpx",
        {
            "version": "1.1",
            "creator": "osm-waypoints",
            "xmlns": GPX_NS,
        },
    )

    metadata = ET.SubElement(gpx, "metadata")
    ET.SubElement(metadata, "name").text = "OSM hiking waypoints"
    ET.SubElement(metadata, "desc").text = (
        "Points of interest extracted from OpenStreetMap for hiking"
    )

    for waypoint in waypoints:
        tags = waypoint.get("tags", {})
        name = to_english(waypoint["name"])
        category = to_english(waypoint["category"])
        symbol = garmin_symbol(waypoint["category"], tags)

        wpt = ET.SubElement(
            gpx,
            "wpt",
            {
                "lat": f"{waypoint['lat']:.7f}",
                "lon": f"{waypoint['lon']:.7f}",
            },
        )

        if waypoint.get("ele") is not None:
            ET.SubElement(wpt, "ele").text = f"{waypoint['ele']:.1f}"

        ET.SubElement(wpt, "name").text = name[:255]

        description = to_english(waypoint.get("description", "")).strip()
        if not description:
            description = category
        ET.SubElement(wpt, "desc").text = description[:1024]

        ET.SubElement(wpt, "type").text = category[:64]
        ET.SubElement(wpt, "sym").text = symbol

    return gpx


def prettify_xml(element: ET.Element) -> str:
    rough = ET.tostring(element, encoding="unicode")
    return minidom.parseString(rough).toprettyxml(indent="  ")


def main() -> int:
    try:
        waypoints = load_waypoints()
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 1

    if not waypoints:
        print("No waypoints to export.")
        return 0

    gpx = build_gpx(waypoints)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    WAYPOINTS_GPX.write_text(prettify_xml(gpx))

    symbols = sorted({garmin_symbol(w["category"], w.get("tags", {})) for w in waypoints})
    print(f"Exported {len(waypoints)} waypoints to {WAYPOINTS_GPX}")
    print(f"Garmin symbols used: {', '.join(symbols)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())