# How Missing-Way Detection Works

This is the algorithm behind `gpx-osm filter-missing` (`missing_filter.py`) — the step that
decides which GPS-traced clusters are genuinely absent from OSM and therefore worth a JOSM
bundle. For the full pipeline (GPX → segments → clusters → bundles) see `docs/architecture.md`;
for field-level detail on `Cluster` see `docs/data-model.md`.

## Why this step exists

Clustering (`clusterer.py`) only answers "did multiple runs trace the same physical stretch?".
It says nothing about whether that stretch is already mapped. `missing_filter.py` is the product
gate: it compares each cluster's geometry against real OSM ways and only lets low-coverage
clusters through to `namer.py` / `osm_extractor.py`. Everything already well-mapped is dropped
here so a mapper's JOSM session only ever contains genuinely new paths.

## The comparison set: "path-like" OSM ways

The filter loads every way in the city PBF whose `highway` tag is in:

```
footway, path, steps, pedestrian, cycleway, bridleway,
residential, service, living_street, track, unclassified
```

`residential` / `service` / `track` / `unclassified` are included deliberately — in HCMC, narrow
motorbike alleys are routinely tagged as one of these (or left untagged) rather than `footway`.
Treating only `footway`/`path` as "exists" would flag thousands of already-mapped alleys as
missing. This way set is extracted once per city PBF and cached at
`output/osm_paths.parquet`, invalidated by PBF mtime (see `load_osm_paths`).

## Per-cluster coverage check

For each cluster's `representative_line` (the longest member segment, already in EPSG:4326):

1. **Project to local UTM** so all distances below are in meters, not degrees.
2. **Bounding-box query** the cached OSM ways via spatial index, padded by
   `EXISTING_PATH_MATCH_BUFFER_M` (default 12m), to get only nearby candidates.
3. **Buffer and union** those candidate ways by the same buffer distance, forming one
   "already-mapped corridor" polygon.
4. **Coverage fraction** = the length of the representative line that falls inside that
   corridor, divided by the line's total length.

```
representative_line  ────────────●═══════════════════●──────────
                                  └── inside corridor ──┘
osm way (buffered ±12m)     ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
                                  ↑
                        coverage_fraction ≈ 0.55 → likely already mapped
```

A short buffer (12m) is intentional: it should only absorb GPS noise and minor line
simplification, not treat a parallel street 20m away as "the same path".

## Missing vs. covered vs. noise

`osm_coverage_fraction` is set on every cluster, then three-way gated:

| Condition | Result |
|---|---|
| `coverage_fraction >= MISSING_COVERAGE_THRESHOLD` (default 0.45) | **Covered** — dropped, not a bundle |
| `coverage_fraction < 0.45` **and** `num_gpx_traces < MIN_CLUSTER_TRACES` (default 2) | **Noise** — dropped as a one-off trace, not a bundle |
| `coverage_fraction < 0.45` **and** `num_gpx_traces >= MIN_CLUSTER_TRACES` | **Missing** — `is_missing = True`, proceeds to naming + extraction |

The 0.45 threshold is deliberately forgiving of partial coverage: a stretch that's 50%+
already-mapped is treated as "this is that way, maybe just simplified/offset", not missing.
The trace-count gate exists because a single noisy GPS trace can wander off a real path for a
few meters and register as "uncovered" — requiring corroboration from a second independent
run is cheaper than trying to model GPS error directly.

## Outputs

- Every cluster (missing or not) gets `osm_coverage_fraction` and `is_missing` written back into
  `output/clusters_state.json`, so downstream stages and reruns see the same verdict.
- Only missing clusters are written to `output/clusters_missing.geojson` for quick inspection
  (e.g. in QGIS) before running `gpx-osm name` / `gpx-osm extract`.
- `MissingFilterSummary` (`clusters_in`, `missing_kept`, `covered_skipped`, `few_traces_skipped`)
  is what `gpx-osm filter-missing` prints — use it to sanity-check a threshold change without
  re-reading the geojson.

## Tuning

| Knob | Effect of raising it |
|---|---|
| `EXISTING_PATH_MATCH_BUFFER_M` | Wider tolerance for "this OSM way counts as the same path" — fewer false "missing" from GPS drift, but risks absorbing genuinely separate parallel paths. |
| `MISSING_COVERAGE_THRESHOLD` | Higher = stricter "must be mostly uncovered to count as missing" → fewer, higher-confidence bundles. Lower = more bundles, more false positives from partially-mapped ways. |
| `MIN_CLUSTER_TRACES` | Higher = require more independent corroborating runs → shorter, more trustworthy list; fewer real paths surfaced from low-traffic routes. |

All three live in `.env` (see `docs/usage.md`) and take effect on the next
`gpx-osm filter-missing` / `make pipeline` run — no code changes needed.

## Known limitations

- Coverage is computed against the **representative line only** (the single longest member
  segment), not every trace in the cluster. A representative that happens to run along an
  already-mapped section while the rest of the cluster covers new ground can under-report
  how much is actually missing.
- The path-like `highway` set is a heuristic, not a certainty — a way tagged `residential` that
  is genuinely a car street (not an alley) still counts as "existing", which can hide missing
  parallel footways that run alongside such roads.
- No attempt is made to distinguish "same way, slightly different tagging class" (e.g. a
  `footway` re-tagged as `path`) from "different path" — anything in `PATH_HIGHWAY_VALUES` counts.
