# Claude Code Prompt: gpx-osm-missing-paths Pipeline

**Copy everything below the `---` line into Claude (claude.ai or Claude Code / Artifacts / Cursor / Windsurf) and ask it to implement the full project.**

---

You are an expert Python geospatial engineer and pragmatic full-stack developer. You follow modern best practices: clean code, type hints everywhere, minimal but powerful deps, excellent error messages, rich CLI output, and thorough documentation.

## Project Goal
Build a complete, reproducible, local-first pipeline that helps OpenStreetMap contributors (especially runners/walkers in cities like Ho Chi Minh City) automatically:

1. Ingest a large collection of raw GPX files from runs/walks (in `./gpx/`, gitignored).
2. Parse, clean, deduplicate and **cluster** GPX track segments that represent the **same physical path** (many traces on one new footpath/alley/stairway).
3. Automatically generate **human-readable, distinct names** for each cluster by querying a local OSM extract for major POIs (cafes, parks, schools, landmarks, named streets) within ~50 meters.
4. For each cluster, **check what already exists in OSM** by producing a small, focused `.osm` extract (with 50m buffer around the cluster geometry) that can be opened directly in JOSM.
5. Bundle, for every cluster: the `.osm` file + **all original GPX segments** belonging to that cluster (in a subfolder) so the mapper has perfect reference data to draw the accurate missing footpath/road in JOSM.

The output lives in `./clusters/{sanitized_cluster_name}/` and is immediately actionable in JOSM + QGIS.

## Non-Negotiable Tech Constraints
- **Python 3.12+**, managed exclusively with `uv` (pyproject.toml, `uv sync`, `uv run`).
- **Makefile** as the primary interface (`make pipeline`, `make process`, `make cluster`, etc.). No raw `python` commands in docs.
- **Typer + Rich** for beautiful CLI (`gpx-osm process`, `gpx-osm cluster`, `gpx-osm name`, `gpx-osm extract`, `gpx-osm pipeline`).
- **Pydantic v2** models for all data (GPXSegment, Cluster, etc.).
- **geopandas + shapely + hdbscan + pyproj** for all geospatial work. Use haversine-aware clustering where possible.
- **Local OSM handling via `osmium` CLI tool** (user installs `osmium-tool` or uses Docker). Never rely on Overpass API or internet after initial setup. Support a master `vietnam-latest.osm.pbf` or city-specific extract.
- **Docker + docker-compose** for optional local OSRM (for future map-matching). Do **not** make the core pipeline depend on a running OSRM server.
- Keep dependencies lean. No heavy PostGIS, no DuckDB unless it dramatically simplifies (prefer pure geopandas + spatial index for POI queries).
- All code in `src/gpx_osm_pipeline/`. Single `cli.py` entrypoint.
- `.env` + `python-dotenv` for configuration. Provide `.env.example`.
- Excellent logging with `rich` (progress bars with `tqdm`, colored status).
- Git-friendly: `gpx/`, `clusters/`, `output/` are gitignored. Samples in `samples/` are committed.

## Detailed Pipeline Steps (Implement Exactly)

### Step 0: Project Skeleton & DX (do this first)
Create the full recommended directory structure (see below). Add:
- Comprehensive `README.md` with quickstart, architecture diagram (ASCII or mermaid), examples for HCMC runners, troubleshooting (common GPX issues, osmium install, memory tips for large PBF).
- `CLAUDE.md` with project-specific rules for future AI sessions (always run `make lint` before committing, prefer simple robust heuristics, update docs when behavior changes, never commit large clusters/, use `uv run`, test with samples first, etc.).
- `docs/` with `architecture.md`, `usage.md` (detailed CLI + env vars + tuning clustering params), `data-model.md`, `osrm-setup.md` (how to cut a HCMC bbox and build small OSRM graph if wanted), `troubleshooting.md`.
- `.gitignore` (already sketched), `pyproject.toml` (deps listed above + dev), `Makefile` (targets for every major step + `pipeline`).
- `docker-compose.yml` with `osrm` service (commented that graph build is heavy).
- `samples/` with 3-4 minimal but realistic GPX files (synthetic short runs around a park or alley, some overlapping, some distinct). Make them valid GPX 1.1 with `<trk><trkseg><trkpt>` + optional `<ele>` and `<time>`. One file with multiple segments.
- Pydantic models in `models.py`.

### Step 1: GPX Processing (`gpx_processor.py`)
- Recursively find all `*.gpx` (and `*.gpx.gz` if easy) in `GPX_DIR`.
- Use `gpxpy` to parse. Handle multiple tracks, multiple `<trkseg>`, extensions (Garmin, Strava, etc.).
- For every trackpoint: validate lat/lon in Vietnam or reasonable bbox (configurable), convert to shapely Point with CRS EPSG:4326.
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
This is the hardest and most important part. Goal: group segments that physically represent the **same** footpath/alley/stairs so they become one "mapping task".

**Recommended practical algorithm (implement this or clearly better variant):**

1. Take all cleaned LineStrings.
2. Create midpoints + length + bearing features.
3. **Rough bucketing**: assign each segment to H3 cells (resolution ~10 or 11, ~ few meters) of its midpoint and start/end. Use `h3` lib? Wait, add `h3` or implement simple geohash. Actually, to avoid new dep, use a simple grid or just proceed to spatial join.
4. **Proximity graph / connected components** (best balance):
   - For every pair of segments that are potentially close (first filter with `geopandas.sjoin` on 30m buffered geometries — this is efficient), compute:
     - Hausdorff distance (shapely)
     - Or better: fraction of length that overlaps when one is buffered 8-12m.
     - Direction similarity (bearing diff < 30°).
   - If Hausdorff < 25m **AND** significant overlap (>40% of shorter length) **OR** they are almost collinear and close, connect them in a graph (use `networkx`? add as optional or implement simple Union-Find / DFS since N not millions).
   - With 5k-20k segments this can be slow if naive O(n^2). Mitigate:
     - Spatial index (geopandas `sindex` or shapely STRtree).
     - Only consider segments whose midpoints are within 100m first.
     - Or use HDBSCAN on **midpoints** (with haversine) to get rough groups, then refine within each bucket with the overlap logic. This hybrid is pragmatic.
5. Assign `cluster_id` (integer) to each segment. Also compute `cluster_size` (how many segments in group).
6. For each cluster, compute a **representative geometry**:
   - Union of all (or top N longest) segments buffered slightly then unary_union, or take the longest segment as "canonical", or implement a simple "centerline" by averaging close parallel lines (advanced, optional — start with longest + note "merged").
   - Store `representative_line` (LineString), total_length_m, num_segments, files list, bbox.
7. Output: `output/clusters_raw.geojson` (one feature per cluster with properties + geometry) and assignment table linking segment_id → cluster_id.

Tune defaults so that 8-15 runs on the same new alley become **one** cluster, while two parallel footpaths 40m apart stay separate.

Document the clustering heuristic clearly in `docs/architecture.md` and `CLAUDE.md` so future changes are easy.

### Step 3: Human-Readable Naming + POI Enrichment (`namer.py`)
For every cluster:

1. Load or prepare a **POI layer** once:
   - On first run (or via `make prepare-pois`), use `osmium export` (or Python osmium if bindings easy) with tag filter for relevant features that have `name=*`:
     - `amenity` (cafe, restaurant, school, hospital, place_of_worship, etc.)
     - `shop`, `tourism`, `leisure` (park, garden), `historic`, `office`, `public_transport` (stop_position, station), `landuse` important ones, `natural`.
   - Export to `output/pois.geojson` or (better) `output/pois.parquet` (geoparquet via pyarrow). Include `osm_id`, `name`, `tags` (json), geometry (point or centroid of way).
   - This file is reused across runs. Rebuild only when OSM extract updates.
2. For the cluster's representative_line (or its 50m buffer polygon):
   - Spatial join / nearest / `sjoin` to find all POIs within `POI_SEARCH_RADIUS_M`.
   - Rank them: prefer named POIs, closer ones, "important" types (park > cafe > shop). Dedup POIs that are very close to each other.
   - Also find the nearest **named highway** or residential street within 80m for "along Foo Street" context.
3. Generate 1-2 sentence human name, e.g.:
   - "Footpath behind Thao Dien Park connecting to Nguyen Van Huong"
   - "New alley near Cafe Sống 99 from residential block to main road"
   - "Stairway shortcut in Phu My Hung greenery near crescent lake"
   - Make it concise, title-case, no special chars for filesystem.
4. Sanitize for directory: `slugify` (implement simple version or use `python-slugify` — add dep if clean). Add numeric suffix if name collision (`_01`, `_02`).
5. Store in Cluster model: `human_name`, `slug`, `nearby_pois` (list of dicts with name/distance/type), `description`.

Write `output/named_clusters.geojson` with rich properties.

### Step 4+5: OSM Existence Check + Per-Cluster JOSM Bundle (`osm_extractor.py`)
For each named cluster:

1. Compute precise **buffered geometry**: `representative_line.buffer(50)` in meters (project to UTM first, buffer, back to 4326) or use shapely `buffer` with degree approx but prefer projected for accuracy.
2. Get bbox or exact polygon of the buffer.
3. **Extract small .osm** using `osmium extract`:
   ```bash
   osmium extract --bbox minlon,minlat,maxlon,maxlat \
     --output clusters/{slug}/{slug}.osm \
     $OSM_PBF_PATH
   ```
   Or use polygon filter if you implement it (more precise, less extra data).
   - The resulting `.osm` contains **everything** JOSM needs in that 50m halo: existing footways, roads, POIs, buildings for context, addresses, etc.
4. Copy (or symlink if safe) **all original GPX files** (or the specific segments) belonging to this cluster into `clusters/{slug}/gpx/`.
   - Also write a small `cluster_meta.json` with: human_name, num_gpx, total_length_m, representative_wkt, nearby_pois, created_at, source_files list, suggested JOSM workflow notes.
5. Optional but nice: also write `representative.geojson` and `all_segments.geojson` (the raw ones in this cluster) inside the folder for QGIS preview.

After this step, user can:
```bash
open clusters/near_thao_dien_park_footpath_01/   # or drag .osm into JOSM
# In JOSM: File → Open the .osm, then drag all .gpx from the gpx/ subfolder
# Compare existing ways vs your traces → draw the missing path perfectly.
```

### Additional Deliverables
- **Incremental / resume support**: keep a `processed_files.json` or use mtimes + hashes. New GPX only trigger re-clustering of affected areas if you want sophistication (start simple: full reprocess is fine for personal use, <10k segments).
- **Summary report**: at end of pipeline, print a nice table (with rich) of all clusters: name | #traces | length | #POIs nearby | .osm size.
- **Visualization (bonus, low priority)**: `make viz` that produces `output/clusters_preview.html` (folium with colored cluster lines + POI markers + popups with names). Useful for overview before JOSM work.
- **Validation**: basic checks (clusters must have >= MIN segments, geometry valid, etc.). Report orphans.
- **Error resilience**: bad GPX files logged + skipped, not crash whole run. One bad segment doesn't poison a cluster.
- **HCMC / Vietnam examples** in README and docs (Thao Dien, Phu My Hung, Nui Dinh trails, Ba Vi, etc.).

## Project Structure (Create Exactly)
```
gpx-osm-missing-paths/
├── .env.example
├── .gitignore
├── Makefile
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
│   └── claude-code-prompt.md   # this file
├── src/
│   └── gpx_osm_pipeline/
│       ├── __init__.py
│       ├── cli.py
│       ├── models.py
│       ├── config.py
│       ├── gpx_processor.py
│       ├── clusterer.py
│       ├── namer.py
│       ├── osm_extractor.py
│       └── utils.py
├── samples/
│   ├── sample_run_park_loop.gpx
│   ├── sample_alley_01.gpx
│   ├── sample_alley_02.gpx
│   └── sample_distinct_path.gpx
├── gpx/          # gitignored - user drops raw files here
├── clusters/     # gitignored - final JOSM bundles
├── output/       # gitignored - intermediate geojson, pois, reports
└── osrm-data/    # gitignored (optional)
```

## Quality Bar & Style
- Every function has type hints + docstring.
- Use `pathlib.Path` everywhere.
- Rich console with panels, progress, tables.
- All file writes atomic or with clear "overwrite?" logic.
- Config is single `Config` Pydantic model loaded from .env + defaults.
- No global state. Pure functions where possible.
- Handle Vietnam edge cases: lots of motorbike alleys, narrow footpaths, GPS multipath in dense areas, rainy season tracks, Vietnamese POI names (UTF-8 everywhere, no mojibake).
- Make names beautiful and useful for a runner-mapper in Saigon: reference local landmarks, "shortcut to", "behind the", "along the canal", "up the hill to pagoda".
- After implementation, update all docs to match reality. Add a `make test-pipeline` that runs on samples/ and asserts reasonable clusters created.

## Final Instructions for You (Claude)
1. Start by creating the directory structure and all empty/placeholder files with good headers.
2. Implement models.py and config.py first (foundation).
3. Then gpx_processor.py — make it robust and well-tested mentally with the samples.
4. Implement clustering carefully; add comments explaining the heuristic and why it's good enough.
5. POI naming and osmium extraction are critical for JOSM UX — make the .osm extracts small and the names delightful.
6. Write beautiful README and CLAUDE.md.
7. At the end, run `make lint` mentally and fix issues. Provide a short "next steps / known limitations" section.
8. If something is ambiguous (e.g. exact clustering distance), choose the pragmatic runner-mapping-friendly default and document it.

You have full creative freedom on internal implementation details as long as the 5 user steps are honored, DX is excellent, and the output is genuinely useful for adding missing paths to OSM from personal run data.

Now begin. Output the created files and a summary of what was built.
