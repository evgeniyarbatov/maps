# Architecture Overview

## High-Level Data Flow

```
~/.cache/osm/<country>-latest.osm.pbf     (dotfiles fetch-osm / launchd)
   │
   ▼ make city  (osmium extract --polygon=osm/<city>.poly)
osm/<city>.osm.pbf                        (default: osm/hcm.osm.pbf)
   │
~/Documents/data/[private]                 (github.com/evgeniyarbatov/[private], git clone/pull)
   │
   ▼ make gpx  (gpx_fetcher.py — parquet tracks → .gpx, optional lat/lon/radius filter)
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

Country PBFs are **not** owned by this repo. They live under `~/.cache/osm`, refreshed weekly by launchd agent `com.arbatov.fetch-osm` (`dotfiles/bin/fetch-osm`) — a private helper repo of the author's. The `Makefile` includes `dotfiles/make/osm-country.mk` only if that repo is checked out at `~/gitRepo/dotfiles`; otherwise `make country` fails with the exact Geofabrik URL and cache path so anyone can fetch the PBF manually and proceed.

| Layer | How | Path |
|-------|-----|------|
| Country | `make country` → `dotfiles/make/osm-country.mk` if present, else manual-download error | `$(OSM_CACHE_DIR)/vietnam-latest.osm.pbf` |
| City | `make city` → `osmium extract --polygon=$(BOUNDARY_POLYGON)` | `osm/hcm.osm.pbf` (default) |
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

## GPX source (`[private]`, personal export repo)

Raw GPX comes from [`github.com/evgeniyarbatov/[private]`](https://github.com/evgeniyarbatov/[private]),
the author's private Strava/Android/Casio activity export repo, pre-simplified (RDP 10m) into one GeoParquet
file per city under `data/parquet/<source>/<city>.parquet` (columns: `name`, `geometry`
LineString EPSG:4326, `city`). It is **not** GPX-specific to this project — it spans every
city the mapper has run in — so `make gpx` (`gpx-osm fetch-gpx`, `gpx_fetcher.py`) accepts an
optional `--lat/--lon/--radius-km` filter to keep only tracks passing within that radius before
writing them out as individual `.gpx` files (coordinates only — the parquet export carries no
per-point time/elevation).

| Layer | How | Path |
|-------|-----|------|
| Checkout | `git clone`/`pull` (`gpx_fetcher.checkout_gpx_data_repo`) | `GPX_DATA_ROOT/[private]` (default `~/Documents/data/[private]`) |
| Per-track GPX | one file per parquet row, optional radius filter | `GPX_DIR/*.gpx` |

The checkout lives outside the project directory (personal data, not project data) and is
re-pulled on every `make gpx` run, matching the read-only relationship this project has with
the shared OSM country cache under `~/.cache/osm`.

## Core Components

### 1. GPX Fetching (`gpx_fetcher.py`)
Checkout/update the `[private]` repo; convert its per-city parquet tracks into `GPX_DIR/*.gpx`,
optionally filtered to those passing within `--radius-km` of `--lat/--lon`.

### 2. Models (`models.py`)
Pydantic v2 models:
- `GPXSegment`: one ~`SEGMENT_CHUNK_LENGTH_M` chunk of a cleaned `<trkseg>`
- `Cluster`: group of segments for one physical path; includes `num_gpx_traces`, `avg_length_m`, `osm_coverage_fraction`
- `POI`: landmark from OSM used for naming
- `Settings`: all tunable parameters + paths

### 3. GPX Processing
- Turn messy real-world GPX into clean LineStrings in EPSG:4326.
- Project to local UTM only when meter-accurate buffering/length is needed.
- **City clip.** Segments whose midpoint falls outside `BOUNDARY_POLYGON` are dropped so
  runs from another city (e.g. Hanoi GPX while mapping HCMC) never appear as "missing"
  against the wrong OSM extract.
- **Chunk long traces.** A run can be 30km and cross dozens of streets; clustering and the
  missing-path filter both need street-sized geometry, not whole-run geometry, or a single
  missing 500m alley gets averaged away inside an otherwise 95%-covered 20km recording. After
  cleaning, each `<trkseg>` is cut into ~`SEGMENT_CHUNK_LENGTH_M` (default 750m) pieces —
  cut by cumulative distance, not by OSM way boundaries, so consecutive chunks share their
  boundary point and there's no gap between them. Each chunk becomes its own `GPXSegment`.

### 4. Clustering Strategy
Seed-based same-stretch matching (not transitive connected components):

1. Project segments to local UTM
2. Candidate pairs by midpoint proximity (`CLUSTER_MIDPOINT_MAX_M`)
3. Match when midpoints are close, buffered overlap of the shorter line is high, and mean point-to-line distance is low (urban GPS tolerant; Hausdorff on 750m lines is not)
4. Greedy assignment: longest segment first as seed; only segments similar to that seed join the cluster (avoids chaining an entire running network into one mega-cluster)
5. Representative geometry = longest member; `num_gpx_traces` = unique source GPX files

JOSM bundles further require `MIN_CLUSTER_TRACES` (default 2) and low OSM coverage.

### 5. Missing-path filter
Compare cluster representative geometry to path-like highways in the **city** PBF. Only low-coverage clusters become JOSM bundles.

### 6. POI-based Naming
One-time export of named features from city PBF → `output/pois.*`. Rank by distance and importance; slugify for directories.

### 7. Per-cluster OSM Extraction
`osmium extract` with ~50m buffer from city PBF. Keeps JOSM files small while giving connection context.

## Why This Stack?

| Concern | Choice | Reason |
|---------|--------|--------|
| Package management | uv | Fast, reproducible |
| CLI | Typer + Rich | Type-safe, pleasant |
| Geospatial | geopandas + shapely | Mature ecosystem |
| Country OSM | dotfiles `fetch-osm` + `~/.cache/osm` | One shared refresh for all personal OSM tools |
| City scope | osmium-tool `extract` + `.poly` | Single host tool, no unpackaged binary |
| Local clips / tags | osmium-tool | Fast, standard |
| Config | pydantic-settings + .env | Validated knobs |

## Non-Goals (for v1)

- Second OSM download/mirror system (use dotfiles, or fetch the PBF manually per the `make country` error message)
- Perfect automatic centerline from noisy traces
- Full map-matching / direct OSM upload
- Web UI

See `README.md` and `CLAUDE.md` for operational guidelines.
