# Troubleshooting

## "No OSM PBF found" / `resolve_osm_pbf()` fails

`Settings.resolve_osm_pbf()` checks, in order: `OSM_PBF_PATH`, the city clip
(`osm/<city>.osm.pbf`), then the country cache (`~/.cache/osm/<country>-latest.osm.pbf`).

- Missing country cache → `make country` (calls dotfiles `fetch-osm`), or wait for the weekly
  launchd job `com.arbatov.fetch-osm`.
- Missing city clip → `make city` (requires the country cache and `BOUNDARY_POLYGON` to exist).
- Run `gpx-osm osm-paths` to see exactly which of the three candidates resolved and whether
  each file exists on disk.

## `osmium: command not found`

`make city` installs `osmium-tool` via Homebrew automatically (`make deps`). Manually:
`brew install osmium-tool`. It's a required host tool; there is no pure-Python fallback
(per project philosophy: pragmatic and local-first, not another dependency to vendor).

## GPX file fails to parse

`gpx_processor.parse_gpx_file` catches per-file exceptions in `process()` — a single corrupt
GPX increments `files_failed` in the summary table but does not abort the run. If you want to
see the actual traceback for a specific file, parse it directly:

```bash
uv run python -c "import gpxpy; gpxpy.parse(open('gpx/bad_file.gpx').read())"
```

Common causes: non-UTF-8 encoding (rare on modern devices), a `<trkseg>` with zero points, or
GPS cold-start points reading `0,0` — reasoning why `gpx_processor.VIETNAM_BBOX` exists: bad
fixes outside a generous Vietnam bounding box are dropped per-point rather than failing the
segment.

## Hundreds of clusters each with only one GPX

Usually one of:

1. **Traces outside the city poly** — e.g. Hanoi runs while `BOUNDARY_POLYGON=osm/hcm.poly`.
   `gpx-osm process` drops those (see “Segments dropped (outside city)” in the summary).
2. **One-off segments** — bundles require `MIN_CLUSTER_TRACES` distinct GPX files (default 2).
   Raise it to `3` or `5` for a shorter, higher-confidence list.
3. **Matching too strict** — raise `CLUSTER_MEAN_DISTANCE_M` / lower `CLUSTER_OVERLAP_FRACTION`
   in `.env`, then re-run from `make cluster`.

Map overview: open `output/clusters_missing.geojson` or `output/named_clusters.geojson` in
geojson.io / QGIS / JOSM.

## A cluster I expected to merge stayed separate (or vice versa)

Tunable in `.env`: `CLUSTER_MEAN_DISTANCE_M`, `CLUSTER_OVERLAP_FRACTION`,
`CLUSTER_MIDPOINT_MAX_M`, `CLUSTER_OVERLAP_BUFFER_M`. Re-run from `make cluster`.

Clustering is seed-based (longest segment first), not transitive connected components — two
segments only merge if each is similar to the same seed, so whole-city running networks no
longer collapse into one mega-cluster.

**Known limitation:** `SEGMENT_CHUNK_LENGTH_M` cuts are by cumulative distance from each
trace's own start, not aligned to physical streets, so two runs can chunk the same real path
at different offsets. Adjacent multi-trace bundles for one long corridor are normal; map
them as separate JOSM sessions or raise chunk length.

## A path I know is missing from OSM didn't get a JOSM bundle

Check `output/clusters_raw.geojson` for that geometry. Common reasons it was skipped:

- `num_gpx_traces` &lt; `MIN_CLUSTER_TRACES` (only one file covered it)
- `osm_coverage_fraction` ≥ `MISSING_COVERAGE_THRESHOLD` (default 0.45) — an existing
  `residential`/`track`/`unclassified` way is treated as covering it
- Midpoint outside `BOUNDARY_POLYGON`

Inspect `output/osm_paths.parquet` if coverage looks wrong.

## Stale `output/osm_paths.parquet` / `pois.parquet` / `named_ways.parquet` after re-clipping the city

These caches are invalidated by comparing file mtimes: if the cache file's mtime is older than
the city PBF's mtime, it's rebuilt automatically. If you replace the PBF without changing its
mtime (e.g. restoring from a backup), delete the relevant `output/*.parquet` file manually.

## `.osm` extract looks empty or “broken” in JOSM

Common causes:

1. **Empty extract** — cluster geometry outside the city PBF (e.g. Hanoi GPX while using
   `osm/hcm.osm.pbf`). The pipeline now drops out-of-city segments and refuses to write an
   empty `.osm`. Re-run `make process` … `make extract`.
2. **Incomplete multipolygons** — older extracts kept country/admin relations with most
   members missing; JOSM draws those as huge red incomplete outlines. Current extracts strip
   incomplete relations after `osmium extract`. Re-run `make extract`.

## Vietnamese names look garbled in file names or JOSM

Everything is UTF-8 end to end; `utils.slugify()` transliterates diacritics to ASCII for
filesystem-safe slugs (directory names), but `human_name` and POI `name` fields keep full
Vietnamese text. If you see mojibake, check your terminal/editor locale, not the pipeline.

## `make lint` fails on a file I didn't touch

Run `uv run ruff check src tests --fix` first for auto-fixable issues, then re-run
`make lint`. `mypy --strict` is configured in `pyproject.toml`; shapely/geopandas types are
occasionally incomplete — prefer a narrow, justified `# type: ignore[code]` over disabling
strict mode project-wide.
