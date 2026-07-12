# Claude Code Prompt: gpx-osm-missing-paths Pipeline

**Copy everything below the `---` line into Claude (claude.ai or Claude Code / Artifacts / Cursor / Windsurf) and ask it to implement the full project.**

---

You are an expert Python geospatial engineer and pragmatic full-stack developer. You follow modern best practices: clean code, type hints everywhere, minimal but powerful deps, excellent error messages, rich CLI output, and thorough documentation.

## Project Goal
Build a complete, reproducible, local-first pipeline that helps OpenStreetMap contributors (especially runners/walkers in cities like Ho Chi Minh City) automatically:

1. Ingest a large collection of raw GPX files from runs/walks (in `./gpx/`, gitignored).
2. Parse, clean, deduplicate and **cluster** GPX track segments that represent the **same physical path** (many traces on one footpath/alley/stairway).
3. **Filter to missing paths only**: for each cluster, compare its geometry against existing OSM ways (footways, paths, steps, residential alleys, etc.) from the **city-scoped local PBF**. **Only keep clusters that are not already mapped** (or only poorly covered) in OSM. Do **not** write JOSM bundles for well-covered paths.
4. Automatically generate **human-readable, distinct names** for each *missing* cluster by querying the city OSM extract for major POIs (cafes, parks, schools, landmarks, named streets) within ~50 meters.
5. For each missing-path cluster only, produce a focused JOSM bundle:
   - Small `.osm` extract (50m buffer around the cluster geometry)
   - All original GPX segments for that cluster (subfolder)
   - **`cluster_meta.json`** documenting at minimum:
     - `num_gpx_traces` — how many GPX traces (segments) are in the cluster
     - `avg_length_m` — average length of those GPX traces in meters
     - plus supporting fields (human name, total/min/max length, source files, etc.)

The output lives in `./clusters/{sanitized_cluster_name}/` and contains **only mapping tasks for paths that appear missing from OSM**.

## OSM data source (non-negotiable — reuse shared cache, do not invent another download flow)

**Do not** implement Geofabrik downloaders, mirrors, or a second refresh daemon in this repo. Country extracts are already maintained by the user's **dotfiles** tooling:

| Piece | Location / role |
|-------|------------------|
| Weekly fetch (launchd) | `~/gitRepo/dotfiles/launchd/com.arbatov.fetch-osm.plist.template` → runs `refresh-osm-cache` |
| Fetcher | `~/gitRepo/dotfiles/bin/fetch-osm` (+ `refresh-osm-cache`) |
| URL list | `~/gitRepo/dotfiles/osm/urls` (e.g. `vietnam-latest.osm.pbf`, …) |
| Shared cache | `~/.cache/osm/<country>-latest.osm.pbf` (`OSM_CACHE_DIR`, `OSM_MAX_AGE_DAYS=7`) |
| Make include | `~/gitRepo/dotfiles/make/osm-country.mk` → `COUNTRY_OSM_PATH`, targets `country` / `osm-country-fetch` |

### Country + city knobs (generic; default HCMC)

```make
URL = https://download.geofabrik.de/asia/vietnam-latest.osm.pbf
include $(HOME)/gitRepo/dotfiles/make/osm-country.mk

OSM_DIR = osm
BOUNDARY_POLYGON ?= osm/hcm.poly          # any city .poly
CITY := $(basename $(notdir $(BOUNDARY_POLYGON)))
CITY_OSM_PBF := $(OSM_DIR)/$(CITY).osm.pbf
```

- **Country**: set `URL` / `OSM_URL` (and matching `OSM_COUNTRY_FILE`) for Vietnam, Thailand, Singapore, etc. `make country` only calls existing `fetch-osm` into `~/.cache/osm`. Never curl Geofabrik from application Python.
- **City**: committed osmconvert boundary polys under `osm/*.poly`. **Default is `osm/hcm.poly`** (Ho Chi Minh City; same poly family as `[private]/osm/hcm.poly`). Clip with:
  ```bash
  osmconvert $(COUNTRY_OSM_PATH) -B=$(BOUNDARY_POLYGON) \
    --complete-ways --complete-multipolygons -o=$(CITY_OSM_PBF)
  osmium cat --overwrite $(CITY_OSM_PBF) -o $(CITY_OSM)
  ```
- Other city: `make city BOUNDARY_POLYGON=osm/hanoi.poly` (add the poly first).
- Other country: `make country URL=https://download.geofabrik.de/asia/thailand-latest.osm.pbf` then a Thailand city poly.
- **Pipeline PBF**: all filter/name/extract steps use **`CITY_OSM_PBF`** (`Settings.resolve_osm_pbf()`), not the full country file, once `make city` has run.
- Host tools required: `osmconvert`, `osmium-tool`. Missing country PBF → clear error pointing at `make country` or launchd `com.arbatov.fetch-osm`.
- Gitignore: `osm/*.osm`, `osm/*.osm.pbf`; **commit** city `osm/*.poly` only.

Config lives in `src/gpx_osm_missing_paths/config.py` (`Settings`: `osm_cache_dir`, `osm_country_file`, `boundary_polygon`, `resolve_osm_pbf()`).

## Non-Negotiable Tech Constraints
- **Python 3.12+**, managed exclusively with `uv` (pyproject.toml, `uv sync`, `uv run`).
- **Makefile** as the primary interface (`make country`, `make city`, `make pipeline`, `make process`, `make cluster`, etc.). No raw `python` commands in docs.
- **Typer + Rich** for beautiful CLI (`gpx-osm process`, `gpx-osm cluster`, `gpx-osm filter-missing`, `gpx-osm name`, `gpx-osm extract`, `gpx-osm osm-paths`).
- **Pydantic v2** models for all data (GPXSegment, Cluster, Settings).
- **geopandas + shapely + hdbscan + pyproj** for all geospatial work. Use haversine-aware clustering where possible.
- **Local OSM only** via shared cache + city poly + `osmium` / `osmconvert`. Never Overpass / internet after the country PBF is on disk. Never a project-local Geofabrik downloader.
- **Docker + docker-compose** for optional local OSRM (for future map-matching). Do **not** make the core pipeline depend on a running OSRM server.
- Keep dependencies lean. No heavy PostGIS, no DuckDB unless it dramatically simplifies (prefer pure geopandas + spatial index for POI queries).
- All code in `src/gpx_osm_missing_paths/`. Single `cli.py` entrypoint (`gpx-osm` console script).
- `.env` + pydantic-settings for configuration. Provide `env.example`.
- Excellent logging with `rich` (progress bars with `tqdm`, colored status).
- Git-friendly: `gpx/`, `clusters/`, `output/`, `osm/*.osm(.pbf)` are gitignored. Samples + `osm/*.poly` are committed.

## Detailed Pipeline Steps (Implement Exactly)

### Step 0: Project Skeleton & DX (do this first)
Create the full recommended directory structure (see below). Add:
- Comprehensive `README.md` with quickstart, architecture diagram (ASCII or mermaid), examples for HCMC runners, troubleshooting (GPX issues, osmium/osmconvert install, **shared OSM cache** / launchd, city poly switching).
- `CLAUDE.md` with project-specific rules (always `make lint`, simple heuristics, never commit large clusters/ or PBF extracts, use `uv run`, test with samples first, **reuse dotfiles OSM cache**, default `osm/hcm.poly`).
- `docs/` with `architecture.md`, `usage.md` (CLI + env + clustering + missing filter + country/city OSM knobs), `data-model.md`, `osrm-setup.md`, `troubleshooting.md`.
- `.gitignore`, `pyproject.toml`, `Makefile` including `$(HOME)/gitRepo/dotfiles/make/osm-country.mk` + `country` / `city` / `pipeline` targets.
- `docker-compose.yml` with optional `osrm` service.
- `osm/hcm.poly` committed (default city). Document adding more `osm/<city>.poly` files.
- `samples/` with 3-4 minimal but realistic GPX files (valid GPX 1.1). One multi-segment file.
- Pydantic models in `models.py`; path resolution in `config.py` (already sketched for OSM).

### Step 1: GPX Processing (`gpx_processor.py`)
- Recursively find all `*.gpx` (and `*.gpx.gz` if easy) in `GPX_DIR`.
- Use `gpxpy` to parse. Handle multiple tracks, multiple `<trkseg>`, extensions (Garmin, Strava, etc.).
- For every trackpoint: validate lat/lon in a configurable bbox (default Vietnam / city bbox derived from poly if easy), convert to shapely Point with CRS EPSG:4326.
- Create `GPXSegment` Pydantic model: original_file, segment_id, geometry (LineString), length_m, num_points, start_time, end_time, bbox, raw_gpx_path (for copying later).
- Cleaning:
  - Remove consecutive duplicate points (within 0.5m).
  - Douglas-Peucker simplify with `SIMPLIFY_TOLERANCE_M` (default 4m).
  - Drop segments shorter than `MIN_SEGMENT_LENGTH_M`.
  - Optional: resample to ~every 5-10m for consistent density (but keep original geometry too).
- Compute WKT or shapely for everything. Project to local UTM (auto-detect zone for Vietnam ~48N/49N) for accurate meter distances when needed, but store final in 4326.
- Output: list of cleaned segments + a manifest parquet/geojson of all segments (for resume/incremental).
- CLI: `gpx-osm process` → shows progress, summary stats (# files, # segments kept, total km), writes `output/segments.geojson` and `output/segments.parquet`.

### Step 2: Deduplication + Clustering (`clusterer.py`)
This is hard and important. Goal: group segments that physically represent the **same** footpath/alley/stairs so they become one candidate mapping task.

**Recommended practical algorithm (implement this or clearly better variant):**

1. Take all cleaned LineStrings.
2. Create midpoints + length + bearing features.
3. **Rough bucketing**: spatial grid / geopandas sjoin (avoid O(n²) without mandatory new deps).
4. **Proximity graph / connected components**:
   - For every pair of segments that are potentially close (filter with `geopandas.sjoin` on ~30m buffered geometries), compute:
     - Hausdorff distance (shapely) and/or fraction of length that overlaps when one is buffered 8-12m.
     - Direction similarity (bearing diff < 30°).
   - If Hausdorff < 25m **AND** significant overlap (>40% of shorter length) **OR** they are almost collinear and close, connect them (networkx optional; Union-Find / DFS is fine).
   - Mitigate cost with spatial index (`sindex` / STRtree), midpoint distance prefilter, or HDBSCAN on midpoints then refine within buckets.
5. Assign `cluster_id` to each segment; compute `cluster_size`.
6. Per cluster **representative geometry** (longest segment is fine for v1) plus:
   - `total_length_m`, `num_segments` / `num_gpx_traces`, **`avg_length_m`**, files list, bbox.
7. Output: `output/clusters_raw.geojson` + segment→cluster assignment table.

Tune defaults so that 8-15 runs on the same new alley become **one** cluster, while two parallel footpaths 40m apart stay separate.

Document the clustering heuristic clearly in `docs/architecture.md` and `CLAUDE.md`.

### Step 3: Missing-Path Filter (`missing_filter.py`)
**Critical step.** Only produce clusters for paths **missing from OSM**. Use **`Settings.resolve_osm_pbf()`** (city extract).

1. Prepare a **local ways layer** once from the city PBF:
   - `osmium tags-filter` + export for path-like highways (`footway`, `path`, `steps`, `pedestrian`, `cycleway`, `bridleway`, plus residential/service/living_street/track/unclassified for Vietnamese alleys).
   - Write `output/osm_paths.parquet` (or geojson). Rebuild when the city PBF mtime changes.
2. Coverage: buffer OSM ways by `EXISTING_PATH_MATCH_BUFFER_M` (~12–15m); compute fraction of representative line covered.
3. **Missing** if coverage < `MISSING_COVERAGE_THRESHOLD` → keep. **Present** → skip (no `clusters/{slug}/`). Prefer slight over-flagging.
4. Write `output/clusters_missing.geojson` with `osm_coverage_fraction`, `is_missing=true`.
5. CLI: `gpx-osm filter-missing` with Rich summary of kept vs skipped.

### Step 4: Human-Readable Naming + POI Enrichment (`namer.py`)
Run **only on missing-path clusters**.

1. POI layer once from the **same city PBF** (`osmium export` / pyosmium), reuse `output/pois.parquet`.
2. Spatial join within `POI_SEARCH_RADIUS_M`; rank by importance + distance; nearest named highway for context.
3. Human name + slugify for filesystem (UTF-8 / Vietnamese safe).
4. Store `human_name`, `slug`, `nearby_pois`, `description`.

Write `output/named_clusters.geojson` (missing only).

### Step 5: Per-Cluster JOSM Bundle (`osm_extractor.py`)
**Only for missing-path named clusters.** Source PBF = city extract via `resolve_osm_pbf()`.

For each cluster:

1. Buffer representative line by `CLUSTER_BUFFER_M` (50m) in projected meters.
2. `osmium extract --bbox …` (or poly) → `clusters/{slug}/{slug}.osm`.
3. Copy relevant GPX into `clusters/{slug}/gpx/`.
4. **Write `cluster_meta.json`** (required):
   ```json
   {
     "human_name": "Footpath behind Thao Dien Park",
     "slug": "footpath_behind_thao_dien_park_01",
     "num_gpx_traces": 12,
     "avg_length_m": 184.6,
     "min_length_m": 160.2,
     "max_length_m": 210.1,
     "total_length_m": 2215.0,
     "representative_length_m": 195.3,
     "osm_coverage_fraction": 0.12,
     "is_missing": true,
     "boundary_polygon": "osm/hcm.poly",
     "city_slug": "hcm",
     "osm_pbf": "osm/hcm.osm.pbf",
     "nearby_pois": [],
     "source_files": ["run_2024_01_05.gpx"],
     "segment_ids": [],
     "created_at": "ISO-8601",
     "josm_notes": "Open the .osm then load gpx/ traces as reference; draw the missing path."
   }
   ```
   Stable field names: **`num_gpx_traces`**, **`avg_length_m`**.
5. Optional: `representative.geojson`, `all_segments.geojson`.

No `clusters/*` for paths already present in OSM.

### Additional Deliverables
- Incremental/resume: full reprocess is fine for personal scale.
- Summary table of **missing** clusters: name | #traces | avg length | coverage % | .osm size; plus skipped count.
- Optional `make viz` (folium) for missing clusters.
- Validation: every `clusters/*/` has `cluster_meta.json` with `num_gpx_traces` + `avg_length_m`.
- Error resilience: bad GPX skipped; missing country/city PBF fails with actionable message (`make country` / `make city` / launchd).
- HCMC examples in README; note generic city/country switch.

## Project Structure (Create Exactly)
```
gpx-osm-missing-paths/
├── env.example
├── .gitignore
├── Makefile                 # includes dotfiles/make/osm-country.mk
├── pyproject.toml
├── docker-compose.yml
├── README.md
├── CLAUDE.md
├── docs/
│   ├── architecture.md
│   ├── usage.md
│   ├── data-model.md
│   ├── osrm-setup.md
│   ├── troubleshooting.md
│   └── claude-code-prompt.md
├── src/
│   └── gpx_osm_missing_paths/
│       ├── __init__.py
│       ├── cli.py
│       ├── models.py
│       ├── config.py          # shared cache + city poly resolution
│       ├── gpx_processor.py
│       ├── clusterer.py
│       ├── missing_filter.py
│       ├── namer.py
│       ├── osm_extractor.py
│       └── utils.py
├── samples/
│   ├── sample_run_park_loop.gpx
│   ├── sample_alley_01.gpx
│   ├── sample_alley_02.gpx
│   └── sample_distinct_path.gpx
├── osm/
│   └── hcm.poly               # default city boundary (committed)
├── gpx/                       # gitignored
├── clusters/                  # gitignored — missing paths only
└── output/                    # gitignored
```

## Quality Bar & Style
- Type hints + short docstring on every public function/model.
- `pathlib.Path` everywhere.
- Rich console with panels, progress, tables.
- Atomic or explicit overwrite file writes.
- Single `Settings` pydantic model from .env + defaults.
- No global state; pure functions where possible.
- Vietnamese UTF-8 everywhere (POI names, slugs carefully).
- After implementation, docs match reality. `make test-pipeline` on samples: only missing clusters under `clusters/`, each with `cluster_meta.json` (`num_gpx_traces`, `avg_length_m`).

## Final Instructions for You (Claude)
1. Honor existing OSM wiring: **dotfiles cache + `make city` poly clip**; do not add a second OSM download subsystem.
2. Implement models + finish config (foundation). Include `num_gpx_traces`, `avg_length_m`, `osm_coverage_fraction` on Cluster.
3. gpx_processor → clusterer → missing_filter (product gate) → namer → osm_extractor.
4. Always write `cluster_meta.json` with trace count and average length; only for missing paths.
5. README / CLAUDE.md document `make country`, `make city`, default `osm/hcm.poly`, and switching country/city.
6. `make lint` clean. Document known limitations.

User outcomes that must hold:
1. Cluster same physical paths from many GPX traces.
2. **GPX + `.osm` bundles only for paths missing from OSM.**
3. Each cluster has **`cluster_meta.json`** with **`num_gpx_traces`** and **`avg_length_m`**.
4. OSM input is **shared `~/.cache/osm` country PBF** clipped by **city `.poly`** (default HCMC), generic for any country/city.
5. Excellent DX for a tired runner mapping in JOSM.

Now begin. Output the created files and a summary of what was built.
