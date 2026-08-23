# Usage

## CLI Commands

All commands run via `uv run gpx-osm <command>`, or the matching `make <target>`.

| Command | Make target | Description |
|---------|-------------|-------------|
| `gpx-osm fetch-gpx` | `make gpx` | Checkout/update `[private]`, convert its parquet tracks into `GPX_DIR` |
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

### Raw GPX source (`make gpx`)

| Variable | Default | Meaning |
|----------|---------|---------|
| `GPX_DATA_REPO_URL` | `https://github.com/evgeniyarbatov/[private].git` | Repo of per-city GeoParquet track exports |
| `GPX_DATA_ROOT` | `~/Documents/data` | Checkout lives at `GPX_DATA_ROOT/[private]` (outside the project dir) |

### Clustering & naming knobs

| Variable | Default | Meaning |
|----------|---------|---------|
| `MIN_SEGMENT_LENGTH_M` | 25 | Drop cleaned chunks shorter than this |
| `SEGMENT_CHUNK_LENGTH_M` | 750 | Cut each cleaned trace into ~this many meters before clustering/coverage checks, so a run up to ~30km doesn't get treated as one giant geometry |
| `SIMPLIFY_TOLERANCE_M` | 4.0 | Douglas-Peucker tolerance (meters, in local UTM) |
| `CLUSTER_BUFFER_M` | 50 | Buffer around a cluster's representative line for the `.osm` extract |
| `POI_SEARCH_RADIUS_M` | 50 | How far to look for naming landmarks |
| `MIN_POI_DISTANCE_M` | 10 | Minimum separation between selected POIs (dedup near-duplicates) |
| `CLUSTER_MIDPOINT_MAX_M` | 200 | Max midpoint separation (m) for candidate pairs |
| `CLUSTER_OVERLAP_BUFFER_M` | 20 | Buffer when measuring overlap of the shorter line |
| `CLUSTER_OVERLAP_FRACTION` | 0.45 | Min fraction of shorter line that must sit near the other |
| `CLUSTER_MEAN_DISTANCE_M` | 20 | Max mean point-to-line distance (m) to treat as same stretch |
| `MIN_CLUSTER_TRACES` | 2 | Min distinct GPX files before a poorly covered cluster becomes a JOSM bundle (raise to 3 for a shorter list) |
| `EXISTING_PATH_MATCH_BUFFER_M` | 12 | Buffer used when computing OSM coverage |
| `MISSING_COVERAGE_THRESHOLD` | 0.45 | Below this fraction covered → cluster is a missing-path candidate |

## Fetching GPX from `[private]`

[`[private]`](https://github.com/evgeniyarbatov/[private]) is a personal export repo of Strava/
Android/Casio activity history, pre-simplified into per-city GeoParquet files (one row per
track, no per-point time/elevation). `make gpx` clones/pulls it into `GPX_DATA_ROOT/[private]`
and writes one `.gpx` file per track into `GPX_DIR`:

```bash
make gpx                                        # every track in [private]
make gpx LAT=10.7940 LON=106.7217 RADIUS_KM=5    # only tracks passing within 5km of a point
make pipeline LAT=10.7940 LON=106.7217 RADIUS_KM=5  # same filter, then the full pipeline
```

`[private]` spans many cities/countries the mapper has run in; LAT/LON/RADIUS_KM keeps only
tracks relevant to the city currently being mapped (all three must be given together, or
omitted together for no filter). `make pipeline` always runs `gpx` first.

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
