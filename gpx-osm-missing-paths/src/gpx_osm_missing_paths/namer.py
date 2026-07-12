"""POI loading (once per city PBF) + human-readable naming for missing clusters only."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import osmium
import shapely.wkb
from pyproj import Transformer
from shapely.geometry import LineString, Point, Polygon

from gpx_osm_missing_paths.clusterer import clusters_to_geodataframe
from gpx_osm_missing_paths.config import Settings
from gpx_osm_missing_paths.models import POI, Cluster, save_clusters_state
from gpx_osm_missing_paths.utils import slugify, utm_epsg_for

POI_TAG_KEYS = ("amenity", "shop", "tourism", "leisure", "craft", "office")
POI_CACHE_NAME = "pois.parquet"
NAMED_WAYS_CACHE_NAME = "named_ways.parquet"

# Rough "how useful is this as a landmark" weight, keyed by "key=value".
IMPORTANCE_BY_CATEGORY: dict[str, float] = {
    "leisure=park": 3.0,
    "tourism=attraction": 3.0,
    "amenity=place_of_worship": 2.5,
    "amenity=university": 2.5,
    "amenity=school": 2.0,
    "amenity=hospital": 2.0,
    "amenity=marketplace": 2.0,
}
DEFAULT_POI_IMPORTANCE = 1.0
NAMED_WAY_IMPORTANCE = 1.5


class _POIHandler(osmium.SimpleHandler):
    """Named nodes/ways with an interesting tag key become point landmarks."""

    def __init__(self) -> None:
        super().__init__()
        self._wkbfab = osmium.geom.WKBFactory()
        self.rows: list[dict[str, object]] = []

    def _category_and_value(self, tags: osmium.osm.TagList) -> str | None:
        for key in POI_TAG_KEYS:
            value = tags.get(key)
            if value:
                return f"{key}={value}"
        return None

    def node(self, n: osmium.osm.Node) -> None:
        name = n.tags.get("name")
        category = self._category_and_value(n.tags)
        if not name or not category:
            return
        self.rows.append(
            {
                "osm_id": n.id,
                "osm_type": "node",
                "name": name,
                "category": category,
                "geometry": Point(n.location.lon, n.location.lat),
            }
        )

    def way(self, w: osmium.osm.Way) -> None:
        name = w.tags.get("name")
        category = self._category_and_value(w.tags)
        if not name or not category or not w.is_closed():
            return
        try:
            wkb = self._wkbfab.create_linestring(w)
        except (RuntimeError, osmium.InvalidLocationError):
            return
        ring = shapely.wkb.loads(wkb, hex=True)
        self.rows.append(
            {
                "osm_id": w.id,
                "osm_type": "way",
                "name": name,
                "category": category,
                "geometry": Polygon(ring.coords).centroid,
            }
        )


class _NamedWayHandler(osmium.SimpleHandler):
    """Named path-like/road ways, kept as lines for 'off <street>' context."""

    def __init__(self) -> None:
        super().__init__()
        self._wkbfab = osmium.geom.WKBFactory()
        self.rows: list[dict[str, object]] = []

    def way(self, w: osmium.osm.Way) -> None:
        name = w.tags.get("name")
        highway = w.tags.get("highway")
        if not name or not highway:
            return
        try:
            wkb = self._wkbfab.create_linestring(w)
        except (RuntimeError, osmium.InvalidLocationError):
            return
        self.rows.append(
            {
                "osm_id": w.id,
                "name": name,
                "highway": highway,
                "geometry": shapely.wkb.loads(wkb, hex=True),
            }
        )


def _load_cached(
    pbf_path: Path, output_dir: Path, cache_name: str, handler_cls: type, empty_columns: list[str]
) -> gpd.GeoDataFrame:
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_path = output_dir / cache_name
    if cache_path.is_file() and cache_path.stat().st_mtime >= pbf_path.stat().st_mtime:
        return gpd.read_parquet(cache_path)

    handler = handler_cls()
    handler.apply_file(str(pbf_path), locations=True)
    if not handler.rows:
        gdf = gpd.GeoDataFrame({c: [] for c in empty_columns}, geometry=[], crs="EPSG:4326")
    else:
        gdf = gpd.GeoDataFrame(handler.rows, geometry="geometry", crs="EPSG:4326")
    gdf.to_parquet(cache_path)
    return gdf


def load_pois(pbf_path: Path, output_dir: Path) -> gpd.GeoDataFrame:
    """Named amenity/shop/tourism/leisure/craft/office features, cached until the PBF changes."""
    return _load_cached(
        pbf_path, output_dir, POI_CACHE_NAME, _POIHandler, ["osm_id", "osm_type", "name", "category"]
    )


def load_named_ways(pbf_path: Path, output_dir: Path) -> gpd.GeoDataFrame:
    """Named highways, cached until the PBF changes (used for 'off <street>' context)."""
    return _load_cached(
        pbf_path, output_dir, NAMED_WAYS_CACHE_NAME, _NamedWayHandler, ["osm_id", "name", "highway"]
    )


def _importance(category: str) -> float:
    return IMPORTANCE_BY_CATEGORY.get(category, DEFAULT_POI_IMPORTANCE)


def rank_pois_for_cluster(
    cluster: Cluster,
    pois: gpd.GeoDataFrame,
    named_ways: gpd.GeoDataFrame,
    settings: Settings,
) -> tuple[list[POI], POI | None]:
    """Nearby POIs ranked by importance/distance, plus the single nearest named street."""
    lon0, lat0 = cluster.representative_line.coords[len(cluster.representative_line.coords) // 2]
    epsg = utm_epsg_for(lon0, lat0)
    to_utm = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
    line_utm = LineString(
        [to_utm.transform(x, y) for x, y in cluster.representative_line.coords]
    )
    radius = settings.poi_search_radius_m

    candidates: list[POI] = []
    if not pois.empty:
        pois_utm = pois.to_crs(epsg=epsg)
        minx, miny, maxx, maxy = line_utm.bounds
        nearby_idx = list(
            pois_utm.sindex.intersection(
                (minx - radius, miny - radius, maxx + radius, maxy + radius)
            )
        )
        for idx in nearby_idx:
            row = pois_utm.iloc[idx]
            distance = row.geometry.distance(line_utm)
            if distance > radius:
                continue
            original = pois.iloc[idx]
            candidates.append(
                POI(
                    osm_id=int(row["osm_id"]),
                    osm_type=str(row["osm_type"]),
                    name=str(row["name"]),
                    category=str(row["category"]),
                    geometry=original.geometry,
                    distance_m=distance,
                    importance=_importance(str(row["category"])),
                )
            )

    candidates.sort(key=lambda p: p.importance / (1.0 + (p.distance_m or 0.0)), reverse=True)

    selected: list[POI] = []
    for candidate in candidates:
        if any(
            candidate.geometry.distance(chosen.geometry) < settings.min_poi_distance_m
            for chosen in selected
        ):
            continue
        selected.append(candidate)
        if len(selected) >= 3:
            break

    nearest_street: POI | None = None
    if not named_ways.empty:
        ways_utm = named_ways.to_crs(epsg=epsg)
        minx, miny, maxx, maxy = line_utm.bounds
        nearby_idx = list(
            ways_utm.sindex.intersection(
                (minx - radius, miny - radius, maxx + radius, maxy + radius)
            )
        )
        best_distance = radius
        for idx in nearby_idx:
            row = ways_utm.iloc[idx]
            distance = row.geometry.distance(line_utm)
            if distance <= best_distance:
                best_distance = distance
                nearest_point_utm = row.geometry.interpolate(row.geometry.project(line_utm.centroid))
                to_wgs84 = Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326", always_xy=True)
                nearest_lon, nearest_lat = to_wgs84.transform(
                    nearest_point_utm.x, nearest_point_utm.y
                )
                nearest_street = POI(
                    osm_id=int(row["osm_id"]),
                    osm_type="way",
                    name=str(row["name"]),
                    category=f"highway={row['highway']}",
                    geometry=Point(nearest_lon, nearest_lat),
                    distance_m=distance,
                    importance=NAMED_WAY_IMPORTANCE,
                )

    return selected, nearest_street


def _length_descriptor(representative_length_m: float) -> str:
    if representative_length_m < 60:
        return "Shortcut"
    if representative_length_m > 400:
        return "Path"
    return "Footpath"


def generate_human_name(
    cluster: Cluster, ranked_pois: list[POI], nearest_street: POI | None
) -> str:
    """Human, locally-flavored name from the strongest nearby landmark(s)."""
    descriptor = _length_descriptor(cluster.representative_length_m)
    if ranked_pois:
        primary = ranked_pois[0]
        name = f"{descriptor} near {primary.name}"
        if nearest_street is not None and nearest_street.name != primary.name:
            name += f", off {nearest_street.name}"
        return name
    if nearest_street is not None:
        return f"{descriptor} off {nearest_street.name}"
    return f"{descriptor} {cluster.cluster_id}"


@dataclass
class NameSummary:
    """Rich-printable counters for ``gpx-osm name``."""

    clusters_named: int = 0
    clusters_without_poi: int = 0


def name_clusters(
    settings: Settings, clusters: list[Cluster]
) -> tuple[list[Cluster], NameSummary]:
    """Generate ``human_name`` / ``slug`` / ``nearby_pois`` for missing clusters only."""
    summary = NameSummary()
    missing = [c for c in clusters if c.is_missing]
    if not missing:
        return clusters, summary

    pbf_path = settings.resolve_osm_pbf()
    pois = load_pois(pbf_path, settings.output_dir)
    named_ways = load_named_ways(pbf_path, settings.output_dir)

    slug_counts: dict[str, int] = {}
    for c in missing:
        ranked, nearest_street = rank_pois_for_cluster(c, pois, named_ways, settings)
        c.nearby_pois = ranked
        c.human_name = generate_human_name(c, ranked, nearest_street)
        base_slug = slugify(c.human_name)
        slug_counts[base_slug] = slug_counts.get(base_slug, 0) + 1
        c.slug = base_slug if slug_counts[base_slug] == 1 else f"{base_slug}_{slug_counts[base_slug]:02d}"
        c.description = (
            f"{c.num_gpx_traces} GPX traces, avg {c.avg_length_m:.0f}m, "
            f"OSM coverage {(c.osm_coverage_fraction or 0.0):.0%}"
        )
        if ranked:
            summary.clusters_named += 1
        else:
            summary.clusters_without_poi += 1

    settings.output_dir.mkdir(parents=True, exist_ok=True)
    gdf = clusters_to_geodataframe(missing)
    gdf["human_name"] = [c.human_name for c in missing]
    gdf["slug"] = [c.slug for c in missing]
    gdf.to_file(settings.output_dir / "named_clusters.geojson", driver="GeoJSON")

    save_clusters_state(settings.output_dir / "clusters_state.json", clusters)
    return clusters, summary
