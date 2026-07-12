# Usage

## CLI Commands

All commands run via `uv run gpx-osm <command>`, or the matching `make <target>`.

| Command | Make target | Description |
|---------|-------------|-------------|
| `gpx-osm process` | `make process` | Parse/clean every GPX under `GPX_DIR` → `output/segments.{geojson,parquet}` |
| `gpx-osm cluster` | `make cluster` | Group overlapping segments → `output/clusters_raw.geojson` |
| `gpx-osm filter-missing` | `make filter-missing` | Keep clusters poorly covered by OSM → `output/clusters_missing.geojson` |
| `gpx-osm name` | `make name` | POI-based human names for missing clusters → `output/named_clusters.geojson` |
| `gpx-osm extract` | `make extract` | Write `clusters/{slug}/` JOSM bundles |
| `gpx-osm pipeline` | `make pipeline` | `city` clip, then all of the above in order |
| `gpx-osm osm-paths` | — | Print resolved country/city/active OSM PBF paths (debug) |

Each stage after `process` reads and rewrites `output/clusters_state.json` — the full working
set of `Cluster` objects — so the pipeline can be run as separate CLI invocations (as the
Makefile does) without recomputing earlier stages.

## Environment Variables

Copy `env.example` to `.env` and adjust. All are optional; defaults target HCMC.

### OSM source (shared cache; see `docs/architecture.md`)

| Variable | Default | Meaning |
|----------|---------|---------|
| `OSM_CACHE_DIR` | `~/.cache/osm` | Where dotfiles `fetch-osm` stores country PBFs |
| `OSM_COUNTRY_FILE` | `vietnam-latest.osm.pbf` | Basename of the cached country PBF |
| `OSM_URL` | Vietnam Geofabrik URL | Used only by `make country` (dotfiles `fetch-osm`) |
| `BOUNDARY_POLYGON` | `osm/hcm.poly` | City clip boundary (osmconvert `.poly`) |
| `OSM_PBF_PATH` | unset | Explicit override; wins over the derived city clip |

### Directories

| Variable | Default |
|----------|---------|
| `GPX_DIR` | `./gpx` |
| `CLUSTERS_DIR` | `./clusters` |
| `OUTPUT_DIR` | `./output` |

### Clustering & naming knobs

| Variable | Default | Meaning |
|----------|---------|---------|
| `MIN_SEGMENT_LENGTH_M` | 25 | Drop cleaned segments shorter than this |
| `SIMPLIFY_TOLERANCE_M` | 4.0 | Douglas-Peucker tolerance (meters, in local UTM) |
| `CLUSTER_BUFFER_M` | 50 | Buffer around a cluster's representative line for the `.osm` extract |
| `POI_SEARCH_RADIUS_M` | 50 | How far to look for naming landmarks |
| `MIN_POI_DISTANCE_M` | 10 | Minimum separation between selected POIs (dedup near-duplicates) |
| `HDBSCAN_MIN_CLUSTER_SIZE` / `HDBSCAN_MIN_SAMPLES` | 8 / 3 | Reserved for a future density-based prefilter; the current clusterer uses a proximity graph (see `docs/architecture.md`) |
| `EXISTING_PATH_MATCH_BUFFER_M` | 12 | Buffer used when computing OSM coverage |
| `MISSING_COVERAGE_THRESHOLD` | 0.45 | Below this fraction covered → cluster is "missing" |

Fine-grained clustering thresholds (Hausdorff distance, overlap fraction, bearing similarity)
are module-level constants in `clusterer.py`, not environment variables — see the comment
block at the top of that file.

## Country / City Switching

```bash
# Another city, same country PBF (add osm/hanoi.poly first)
make city BOUNDARY_POLYGON=osm/hanoi.poly
make pipeline BOUNDARY_POLYGON=osm/hanoi.poly

# Another country (cache basename must match Geofabrik file)
make country URL=https://download.geofabrik.de/asia/thailand-latest.osm.pbf
# then point BOUNDARY_POLYGON at a Thailand city .poly
```

## Testing Against Samples

```bash
make setup
cp -r samples/*.gpx gpx/            # gpx/ is gitignored; samples/ is committed
make city                           # requires the Vietnam PBF in ~/.cache/osm
make process cluster filter-missing name extract
ls clusters/
```

`sample_alley_01.gpx` and `sample_alley_02.gpx` are two independent traces of the same ~150m
alley (offset by a few meters of simulated GPS noise) — they should merge into one cluster.
`sample_run_park_loop.gpx` exercises multi-`<trkseg>` handling (a paused-GPS park loop) and
Garmin `TrackPointExtension` heart-rate data. `sample_distinct_path.gpx` is a different physical
path a few kilometers away and should stay in its own cluster.
