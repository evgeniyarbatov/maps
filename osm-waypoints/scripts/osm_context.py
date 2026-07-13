"""Collect OSM attributes useful for waypoint descriptions."""

from __future__ import annotations

from typing import Any

# Explicit tags commonly useful for short visitor-facing descriptions.
DIRECT_TAGS = (
    "name:en",
    "name",
    "alt_name",
    "official_name",
    "loc_name",
    "short_name",
    "old_name",
    "description",
    "description:en",
    "note",
    "wikipedia",
    "wikipedia:en",
    "wikidata",
    "tourism",
    "historic",
    "natural",
    "amenity",
    "building",
    "man_made",
    "leisure",
    "place",
    "religion",
    "denomination",
    "sect",
    "heritage",
    "heritage:operator",
    "heritage:website",
    "inscription",
    "subject",
    "artist_name",
    "architect",
    "start_date",
    "end_date",
    "year_built",
    "opened",
    "ruins",
    "ele",
    "elevation",
    "height",
    "direction",
    "material",
    "operator",
    "operator:type",
    "access",
    "fee",
    "addr:place",
    "addr:hamlet",
    "addr:suburb",
    "addr:city",
    "addr:street",
    "information",
    "board_type",
    "artwork_type",
    "castle_type",
    "memorial",
    "memorial:conflict",
    "tower:type",
    "cave_entrance",
)

# Extra prefixes for localized names and heritage refs.
TAG_PREFIXES = ("name:", "heritage:", "addr:")


def parse_elevation(tags: dict[str, str], node_ele: float | None = None) -> float | None:
    for key in ("ele", "elevation"):
        value = tags.get(key)
        if value:
            try:
                return float(value.split()[0])
            except ValueError:
                continue
    return node_ele


def build_description_context(poi: dict[str, Any]) -> dict[str, str | float]:
    """Return a compact, description-focused view of OSM data for one POI."""
    tags = poi.get("tags", {})
    context: dict[str, str | float] = {
        "category": poi.get("category", ""),
        "display_name": poi.get("name", ""),
    }

    elevation = parse_elevation(tags, poi.get("ele"))
    if elevation is not None:
        context["elevation_m"] = elevation

    lat = poi.get("lat")
    lon = poi.get("lon")
    if lat is not None and lon is not None:
        context["coordinates"] = f"{lat:.5f}, {lon:.5f}"

    seen_keys: set[str] = set()
    for key in DIRECT_TAGS:
        value = tags.get(key, "").strip()
        if value:
            context[key] = value
            seen_keys.add(key)

    for tag_key, value in sorted(tags.items()):
        if tag_key in seen_keys or not value.strip():
            continue
        if tag_key.startswith(TAG_PREFIXES) and tag_key not in context:
            context[tag_key] = value.strip()

    return context
