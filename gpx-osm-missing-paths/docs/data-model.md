# Data Model

All models are Pydantic v2 (`src/gpx_osm_missing_paths/models.py`), `arbitrary_types_allowed=True`
so shapely geometries can live directly on the model. Geometry fields serialize to WKT via
`field_serializer` for JSON/state round-trips; GeoDataFrame outputs keep real shapely objects.

## `GPXSegment`

One ~`SEGMENT_CHUNK_LENGTH_M` (default 750m) chunk of a cleaned `<trkseg>`. A raw `<trkseg>`
can span a 30km run; `gpx_processor` cuts it by cumulative distance into street-sized chunks
before this model is constructed, so clustering and OSM-coverage checks operate at the
granularity a single missing path actually needs (see `docs/architecture.md`).

| Field | Type | Notes |
|-------|------|-------|
| `segment_id` | `str` | `"{original_file}#t{track_index}s{segment_index}c{chunk_index}"` |
| `source_file` | `Path` | Absolute path, used to copy the raw GPX into a bundle |
| `original_file` | `str` | Path relative to `GPX_DIR`, used as the display/source label |
| `track_index` / `segment_index` | `int` | Position of the source `<trkseg>` within the file |
| `chunk_index` | `int` | Position of this chunk within that `<trkseg>` |
| `geometry` | `LineString` | Cleaned, simplified, EPSG:4326 |
| `length_m` | `float` | Haversine length after cleaning |
| `num_points` | `int` | After dedup, before simplification |
| `start_time` / `end_time` | `datetime \| None` | First/last point with a timestamp |
| `bbox` | `(minx, miny, maxx, maxy)` | EPSG:4326 |

## `Cluster`

A group of segments believed to trace the same physical path.

| Field | Type | Notes |
|-------|------|-------|
| `cluster_id` | `str` | `"cluster_0000"`, stable within one clustering run |
| `segment_ids` | `list[str]` | Member `GPXSegment.segment_id`s |
| `representative_line` | `LineString` | The longest member segment's geometry (v1 heuristic) |
| `num_gpx_traces` | `int` | **Stable field name** — required in every `cluster_meta.json` |
| `avg_length_m` | `float` | **Stable field name** — required in every `cluster_meta.json` |
| `min_length_m` / `max_length_m` / `total_length_m` | `float` | Across member segments |
| `representative_length_m` | `float` | Length of `representative_line` specifically |
| `bbox` | tuple | EPSG:4326 |
| `source_files` | `list[str]` | Unique `original_file` values across members |
| `osm_coverage_fraction` | `float \| None` | Set by `missing_filter.py` |
| `is_missing` | `bool \| None` | Set by `missing_filter.py`; product gate for `osm_extractor.py` |
| `human_name` / `slug` | `str \| None` | Set by `namer.py`, missing clusters only |
| `nearby_pois` | `list[POI]` | Set by `namer.py` |
| `description` | `str \| None` | One-line summary for `cluster_meta.json` |
| `created_at` | `datetime` | Set when the cluster is first built |

`Cluster.to_meta_dict()` produces the exact dict written to `cluster_meta.json`.
`Cluster.to_state_dict()` / `Cluster.from_state_dict()` (plus module-level
`save_clusters_state()` / `load_clusters_state()`) round-trip the full object through
`output/clusters_state.json` between separate CLI invocations.

## `POI`

A named OSM landmark used to generate a human-readable cluster name.

| Field | Type | Notes |
|-------|------|-------|
| `osm_id` | `int` | OSM node/way id |
| `osm_type` | `str` | `"node"` or `"way"` |
| `name` | `str` | From the OSM `name` tag |
| `category` | `str` | `"key=value"`, e.g. `"leisure=park"` |
| `geometry` | `Point` | Node location, or way centroid |
| `distance_m` | `float \| None` | Distance from the cluster's representative line |
| `importance` | `float` | Ranking weight (see `namer.IMPORTANCE_BY_CATEGORY`) |

## `Settings`

`src/gpx_osm_missing_paths/config.py`. See `docs/usage.md` for the full environment variable
table; the key architectural point is `Settings.resolve_osm_pbf()`, which prefers an explicit
`OSM_PBF_PATH`, then the city clip (`osm/<city>.osm.pbf`), then the raw country cache.

## `cluster_meta.json` (per-bundle output)

```json
{
  "human_name": "Footpath near Thao Dien Park",
  "slug": "footpath_near_thao_dien_park",
  "num_gpx_traces": 2,
  "avg_length_m": 150.2,
  "min_length_m": 148.9,
  "max_length_m": 151.5,
  "total_length_m": 300.4,
  "representative_length_m": 151.5,
  "osm_coverage_fraction": 0.0,
  "is_missing": true,
  "nearby_pois": [{"name": "Thao Dien Park", "category": "leisure=park", "distance_m": 32.1}],
  "source_files": ["sample_alley_01.gpx", "sample_alley_02.gpx"],
  "segment_ids": ["sample_alley_01.gpx#t0s0", "sample_alley_02.gpx#t0s0"],
  "description": "2 GPX traces, avg 150m, OSM coverage 0%",
  "created_at": "2024-01-12T06:05:20",
  "bbox": [106.7385, 10.8045, 106.7398, 10.8046],
  "boundary_polygon": "osm/hcm.poly",
  "city_slug": "hcm",
  "osm_pbf": "/Users/you/gitRepo/gpx-osm-missing-paths/osm/hcm.osm.pbf",
  "josm_notes": "Open footpath_near_thao_dien_park.osm in JOSM, then load the files in gpx/ as GPX reference layers. Draw the missing path where the traces agree."
}
```
