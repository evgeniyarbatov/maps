# Roadmap

Goal: surface more real missing ways from a personal GPX collection, with fewer false positives and less JOSM time per way.

## 1. Measure precision

- Record each bundle's outcome (`mapped`, `already_mapped`, `not_a_path`, `skipped`) in a `reviewed.json` under `CLUSTERS_DIR`.
- Print precision per run, and per knob setting, so `MISSING_COVERAGE_THRESHOLD` / `MIN_CLUSTER_TRACES` are tuned against data rather than intuition.
- Skip already-reviewed clusters on later runs, matched by geometry rather than slug.

## 2. Sharper coverage check

- Compute coverage across all member traces, not only the representative line.
- Count pedestrian areas (`highway=pedestrian` + `area=yes`, park footway areas) as mapped.
- Use a separate, tighter buffer for `residential`/`unclassified` roads so footways running beside them aren't hidden.
- Flag partial matches (a way exists but the cluster extends past its end) as "extend way" bundles instead of dropping them.

## 3. Recall

- Merge adjacent chunks of one corridor into a single bundle instead of one per 750m chunk.
- Add a lower-confidence tier for single-trace clusters with very low coverage, ranked below corroborated ones.

## 4. Scale to thousands of runs

- Process GPX incrementally, cached by file hash, so a new run only reprocesses itself.
- Rank bundles by traces × length and write one overview GeoJSON for triage before opening JOSM.
- Bound memory on large collections by streaming segments per chunk of files.

## 5. Better input signal

- Use timestamps from raw GPX (the parquet exports have none) to drop driving/cycling segments by speed.
- Derive the GPS sanity bbox from `BOUNDARY_POLYGON` instead of a hardcoded Vietnam box.

## 6. Other cities

- Run Hanoi end to end as the first non-HCMC city and record what breaks.
- Commit `.poly` boundaries for other cities the GPX collection already covers.
