# Architecture Overview

## High-Level Data Flow

```
~/.cache/osm/<country>-latest.osm.pbf     (dotfiles fetch-osm / launchd)
   │
   ▼ make city  (osmconvert -B=osm/<city>.poly)
osm/<city>.osm.pbf                        (default: osm/hcm.osm.pbf)
   │
gpx/*.gpx
   │
   ▼ gpx_processor.py
cleaned GPXSegment objects (LineString + metadata)
   │
   ▼ clusterer.py
Cluster objects (grouped segments + representative_line)
   │
   ▼ missing_filter.py  (coverage vs OSM ways in city PBF)
missing clusters only (is_missing, osm_coverage_fraction)
   │
   ▼ namer.py  (POIs from city PBF)
named Cluster objects (human_name, slug, nearby_pois)
   │
   ▼ osm_extractor.py
clusters/{slug}/
   ├── {slug}.osm          (osmium extract, 50m buffer from city PBF)
   ├── cluster_meta.json   (num_gpx_traces, avg_length_m, …)
   ├── representative.geojson
   └── gpx/ (copies of relevant raw files)
```

## OSM source (shared cache — no project-local download)

Country PBFs are **not** owned by this repo. They live under `~/.cache/osm`, refreshed weekly by launchd agent `com.arbatov.fetch-osm` (`dotfiles/bin/fetch-osm`).

| Layer | How | Path |
|-------|-----|------|
| Country | `make country` → `dotfiles/make/osm-country.mk` | `$(OSM_CACHE_DIR)/vietnam-latest.osm.pbf` |
| City | `make city` → `osmconvert -B=$(BOUNDARY_POLYGON)` | `osm/hcm.osm.pbf` (default) |
| Per-cluster | `osmium extract --bbox` | `clusters/{slug}/{slug}.osm` |

**Defaults:** Vietnam country extract + `osm/hcm.poly` (Ho Chi Minh City).

**Generic switch:**

```bash
# Another city (same country)
make city BOUNDARY_POLYGON=osm/hanoi.poly
make pipeline BOUNDARY_POLYGON=osm/hanoi.poly

# Another country (must exist in cache / OSM_URL)
make country URL=https://download.geofabrik.de/asia/thailand-latest.osm.pbf
# then BOUNDARY_POLYGON pointing at a Thailand city .poly
```

Python resolution: `Settings.resolve_osm_pbf()` prefers `OSM_PBF_PATH`, then city clip, then country cache (`src/gpx_osm_missing_paths/config.py`).

## Core Components

### 1. Models (`models.py`)
Pydantic v2 models:
- `GPXSegment`: one continuous `<trkseg>` after cleaning
- `Cluster`: group of segments for one physical path; includes `num_gpx_traces`, `avg_length_m`, `osm_coverage_fraction`
- `POI`: landmark from OSM used for naming
- `Settings`: all tunable parameters + paths

### 2. GPX Processing
- Turn messy real-world GPX into clean LineStrings in EPSG:4326.
- Project to local UTM only when meter-accurate buffering/length is needed.

### 3. Clustering Strategy
Hybrid spatial index + overlap graph (or HDBSCAN on midpoints + refine):

1. Rough spatial bucketing on midpoints
2. Within-bucket proximity: buffer overlap + Hausdorff + bearing
3. Connected components → `cluster_id`
4. Representative geometry (longest segment for v1)

Err on slight over-clustering; user can split in JOSM.

### 4. Missing-path filter
Compare cluster representative geometry to path-like highways in the **city** PBF. Only low-coverage clusters become JOSM bundles.

### 5. POI-based Naming
One-time export of named features from city PBF → `output/pois.*`. Rank by distance and importance; slugify for directories.

### 6. Per-cluster OSM Extraction
`osmium extract` with ~50m buffer from city PBF. Keeps JOSM files small while giving connection context.

## Why This Stack?

| Concern | Choice | Reason |
|---------|--------|--------|
| Package management | uv | Fast, reproducible |
| CLI | Typer + Rich | Type-safe, pleasant |
| Geospatial | geopandas + shapely | Mature ecosystem |
| Country OSM | dotfiles `fetch-osm` + `~/.cache/osm` | One shared refresh for all personal OSM tools |
| City scope | `osmconvert` + `.poly` | Same pattern as [private] / [private] |
| Local clips / tags | osmium-tool | Fast, standard |
| Config | pydantic-settings + .env | Validated knobs |

## Non-Goals (for v1)

- Second OSM download/mirror system (use dotfiles)
- Perfect automatic centerline from noisy traces
- Full map-matching / direct OSM upload
- Web UI

See `README.md` and `CLAUDE.md` for operational guidelines.
