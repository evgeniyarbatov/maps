"""Map OSM POI categories to Garmin waypoint symbols."""

from __future__ import annotations

# Symbols verified against Garmin 62s / BaseCamp icon names.
CATEGORY_SYMBOLS: dict[str, str] = {
    "tourism=viewpoint": "Scenic Area",
    "natural=peak": "Summit",
    "tourism=museum": "Museum",
    "tourism=artwork": "Museum",
    "tourism=picnic_site": "Picnic Area",
    "tourism=attraction": "Park",
    "building=church": "Church",
    "building=cathedral": "Church",
    "building=chapel": "Church",
    "building=mosque": "Building",
    "building=temple": "Building",
    "building=pagoda": "Building",
    "natural=cave_entrance": "Tunnel",
    "man_made=tower": "Short Tower",
    "man_made=water_well": "Drinking Water",
}

HISTORIC_SYMBOLS: dict[str, str] = {
    "memorial": "Bell",
    "monument": "Bell",
    "castle": "Building",
    "ruins": "Mine",
    "archaeological_site": "Mine",
    "fort": "Building",
    "battlefield": "Flag, Red",
    "tomb": "Cemetery",
    "wayside_cross": "Crossing",
    "wayside_shrine": "Building",
    "city_gate": "Building",
    "tower": "Short Tower",
    "mine": "Mine",
    "building": "Building",
    "church": "Church",
    "yes": "Building",
}

CHRISTIAN_RELIGIONS = {
    "christian",
    "catholic",
    "protestant",
    "orthodox",
    "anglican",
    "evangelical",
    "baptist",
    "lutheran",
    "methodist",
}


def garmin_symbol(category: str, tags: dict[str, str] | None = None) -> str:
    """Return a Garmin-compatible GPX <sym> value for a POI."""
    tags = tags or {}

    if category in CATEGORY_SYMBOLS:
        return CATEGORY_SYMBOLS[category]

    if category.startswith("historic="):
        historic_type = tags.get("historic", category.split("=", 1)[-1])
        return HISTORIC_SYMBOLS.get(historic_type, "Building")

    if category == "amenity=place_of_worship":
        religion = tags.get("religion", "").lower()
        building = tags.get("building", "").lower()

        if religion in CHRISTIAN_RELIGIONS or building in {"church", "cathedral", "chapel"}:
            return "Church"
        if religion == "muslim" or building == "mosque":
            return "Building"
        if religion in {"buddhist", "hindu", "taoist", "shinto"} or building in {
            "temple",
            "pagoda",
        }:
            return "Building"
        return "Building"

    if "tower" in category:
        return "Tall Tower" if tags.get("man_made") == "tower" else "Short Tower"
    if "peak" in category or "summit" in category:
        return "Summit"
    if "viewpoint" in category or "scenic" in category:
        return "Scenic Area"
    if "museum" in category:
        return "Museum"
    if "picnic" in category:
        return "Picnic Area"
    if "cave" in category:
        return "Tunnel"
    if "church" in category or "worship" in category:
        return "Church"

    return "Flag, Blue"