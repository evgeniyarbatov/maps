"""OSM tag rules for points of interest relevant to hiking."""

from __future__ import annotations

POI_RULES: list[dict[str, str | None]] = [
    {"tourism": "viewpoint"},
    {"tourism": "attraction"},
    {"tourism": "museum"},
    {"tourism": "artwork"},
    {"tourism": "picnic_site"},
    {"amenity": "place_of_worship"},
    {"building": "temple"},
    {"building": "church"},
    {"building": "cathedral"},
    {"building": "chapel"},
    {"building": "mosque"},
    {"building": "pagoda"},
    {"historic": None},
    {"natural": "peak"},
    {"natural": "cave_entrance"},
    {"man_made": "tower"},
    {"man_made": "water_well"},
]


def matches_poi(tags: dict[str, str]) -> str | None:
    """Return a category label if tags match a POI rule, else None."""
    for rule in POI_RULES:
        for key, value in rule.items():
            tag_value = tags.get(key)
            if tag_value is None:
                continue
            if value is None or tag_value == value:
                if value is None:
                    return f"{key}={tag_value}"
                return f"{key}={value}"
    return None


def poi_display_name(tags: dict[str, str]) -> str:
    for key in ("name:en", "name", "alt_name", "official_name"):
        if tags.get(key):
            return tags[key]
    return "Unnamed POI"