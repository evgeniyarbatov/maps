# Troubleshooting

## "No OSM PBF found" / `resolve_osm_pbf()` fails

`Settings.resolve_osm_pbf()` checks, in order: `OSM_PBF_PATH`, the city clip
(`osm/<city>.osm.pbf`), then the country cache (`~/.cache/osm/<country>-latest.osm.pbf`).

- Missing country cache → `make country` (calls dotfiles `fetch-osm`), or wait for the weekly
  launchd job `com.arbatov.fetch-osm`.
- Missing city clip → `make city` (requires the country cache and `BOUNDARY_POLYGON` to exist).
- Run `gpx-osm osm-paths` to see exactly which of the three candidates resolved and whether
  each file exists on disk.

## `osmium: command not found` / `osmconvert: command not found`

Install via Homebrew: `brew install osmium-tool osmctools`. These are required host tools;
there is no pure-Python fallback (per project philosophy: pragmatic and local-first, not
another dependency to vendor).

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

## A cluster I expected to merge stayed separate (or vice versa)

Clustering thresholds live as module constants at the top of `clusterer.py`
(`HAUSDORFF_THRESHOLD_M`, `OVERLAP_FRACTION_THRESHOLD`, `BEARING_THRESHOLD_DEG`,
`OVERLAP_BUFFER_M`), not environment variables — tune there, then re-run `make cluster`.
Remember clustering intentionally favors over-merging; splitting an over-merged cluster in
JOSM is far cheaper than mapping 15 near-duplicate un-merged traces.

**Known limitation:** `SEGMENT_CHUNK_LENGTH_M` cuts are by cumulative distance from each
trace's own start, not aligned to physical streets, so two runs can chunk the same real path
at different offsets — one run's chunk boundary lands mid-path while another's doesn't. That
path may then show up as two adjacent, weakly-clustered bundles instead of one. If you see
this, either merge them in JOSM or lower `OVERLAP_FRACTION_THRESHOLD` in `clusterer.py`.

## A path I know is missing from OSM didn't get a JOSM bundle

Check `output/clusters_raw.geojson` for `osm_coverage_fraction` on that cluster. If it's above
`MISSING_COVERAGE_THRESHOLD` (default 0.45), an existing OSM way is being counted as covering
it — often a `residential`/`track`/`unclassified` way that technically follows the same
corridor. Widen `EXISTING_PATH_MATCH_BUFFER_M` down or inspect `output/osm_paths.parquet` to
see which way is causing the match.

## Stale `output/osm_paths.parquet` / `pois.parquet` / `named_ways.parquet` after re-clipping the city

These caches are invalidated by comparing file mtimes: if the cache file's mtime is older than
the city PBF's mtime, it's rebuilt automatically. If you replace the PBF without changing its
mtime (e.g. restoring from a backup), delete the relevant `output/*.parquet` file manually.

## Vietnamese names look garbled in file names or JOSM

Everything is UTF-8 end to end; `utils.slugify()` transliterates diacritics to ASCII for
filesystem-safe slugs (directory names), but `human_name` and POI `name` fields keep full
Vietnamese text. If you see mojibake, check your terminal/editor locale, not the pipeline.

## `make lint` fails on a file I didn't touch

Run `uv run ruff check src tests --fix` first for auto-fixable issues, then re-run
`make lint`. `mypy --strict` is configured in `pyproject.toml`; shapely/geopandas types are
occasionally incomplete — prefer a narrow, justified `# type: ignore[code]` over disabling
strict mode project-wide.
