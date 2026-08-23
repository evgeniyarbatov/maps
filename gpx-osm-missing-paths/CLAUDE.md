# CLAUDE.md — Instructions for AI Coding Assistants (Claude, Cursor, etc.)

This file contains project-specific rules and context. **Always follow these when working on gpx-osm-missing-paths.**

## Core Philosophy
- This tool exists to help **human mappers** add high-quality missing footpaths, alleys, stairs, and informal paths to OpenStreetMap using their own run/walk GPX data.
- Prioritize **pragmatic, robust, local-first** solutions over clever ML or perfect algorithms.
- The end user (often a runner in HCMC/Saigon) will spend time in **JOSM**, not in this CLI. The pipeline's job is to organize data so JOSM work is fast, accurate, and enjoyable.
- "Good enough clustering + delightful names + perfect JOSM bundles" > 99% perfect clustering that takes 10x longer to implement.

## Always Do
- Run `make lint` (ruff + mypy) and fix issues before considering a change complete.
- Use `uv run` for everything (never bare `python` or `pip`).
- Update **relevant docs/** and this `CLAUDE.md` when behavior, params, or architecture changes meaningfully.
- Test changes against `samples/` first. Add new sample GPX files when introducing new GPX edge cases (multi-segment, elevation, bad timestamps, Vietnamese names, etc.).
- Prefer **simple heuristics + spatial joins** over complex graph algorithms or external services unless the gain is obvious.
- Keep cluster names **human and local** (Vietnamese landmarks, "shortcut", "behind", "along the canal", "to the pagoda"). They are used as directory names and JOSM context.
- Write type hints + short docstrings on every public function and model.
- Use `pathlib.Path` and Pydantic v2 models exclusively for configuration and data transfer.
- Make progress visible with `rich` + `tqdm`. The CLI should feel alive and informative even on 500+ GPX files.
- Handle UTF-8 / Vietnamese text correctly everywhere (POI names, file names, logs).
- Resolve OSM via `Settings.resolve_osm_pbf()` (city clip preferred). Default city poly is `osm/hcm.poly`.
- Emit JOSM bundles **only** for clusters classified as missing from OSM; each bundle needs `cluster_meta.json` with `num_gpx_traces` and `avg_length_m`.

## Never Do
- Commit anything inside `gpx/`, `clusters/`, `output/`, or large `.osm`/`.pbf` files (city `osm/*.poly` boundaries are OK).
- Implement a second Geofabrik/OSM download or refresh system. Country PBF comes from **dotfiles** `fetch-osm` / launchd `com.arbatov.fetch-osm` → `~/.cache/osm`, via `include $(HOME)/gitRepo/dotfiles/make/osm-country.mk` when that private repo is present. When it isn't (e.g. a clone without dotfiles), `make country` must fail with the exact URL/path to fetch manually — never add a fallback downloader.
- Rely on internet/Overpass after the country PBF is cached. City work is local `osmium` on `CITY_OSM_PBF`.
- Introduce heavy services (PostGIS, full DuckDB spatial, Elasticsearch) without strong justification and Makefile opt-in.
- Make the core `make pipeline` depend on a running OSRM server. OSRM is advanced/optional only.
- Use magic numbers without named constants in `config.py` or clear comments.
- Generate directories with spaces or special filesystem chars in cluster slugs.
- Assume the user has a powerful machine. Keep memory usage reasonable (process in chunks if needed for very large collections).

## Workflow When Asked to Implement or Modify a Feature
1. Read the relevant section in `docs/architecture.md` and `docs/usage.md`.
2. Check `models.py` and `config.py` for existing contracts.
3. Implement in small, reviewable steps (e.g., first get processor working cleanly on samples, then clustering, then naming).
4. After code works, update the example output in docs if behavior changed.
5. Run the full `make pipeline` on samples and inspect the generated `clusters/` structure manually.
6. Update `README.md` quickstart or examples if user-visible behavior changed.

## Key Files & Their Responsibilities
- `src/gpx_osm_missing_paths/models.py` — Single source of truth for `GPXSegment`, `Cluster`, `POI`.
- `config.py` — Loads `.env` + defaults into Pydantic `Settings` (shared OSM cache, city poly, clustering knobs).
- `gpx_fetcher.py` — Checkout `[private]` repo + convert its parquet tracks into `GPX_DIR/*.gpx` (writes raw GPX XML directly, no `gpxpy`, so `gpx_processor.py` stays the only `gpxpy` touchpoint).
- `gpx_processor.py` — The only place that touches `gpxpy`. Produces clean segments.
- `clusterer.py` — Documented clustering heuristic. Algorithm changes → update comment + architecture doc.
- `missing_filter.py` — Coverage vs OSM ways; product gate for which clusters get bundles.
- `namer.py` — POI loading (once), spatial queries, name generation logic.
- `osm_extractor.py` — `osmium` extracts + buffer math + bundle writing (`cluster_meta.json`). Atomic writes preferred.
- `cli.py` — Typer commands only. Thin orchestration + pretty printing.
- `utils.py` — Small pure helpers (haversine, bearing, slugify, UTM zone guess, etc.).
- `Makefile` — `gpx` / `country` / `city` / pipeline; includes `dotfiles/make/osm-country.mk`.
- `osm/*.poly` — Committed city boundaries (default `hcm.poly`).

## Clustering Heuristic Notes (Important Context)
Seed-based same-stretch matching: midpoint proximity + buffered overlap + mean distance, greedy longest-first seeds (not transitive connected components — those merged whole running networks).
`num_gpx_traces` is unique GPX files. Bundles require `MIN_CLUSTER_TRACES` (default 2) and low OSM coverage.
Primary knobs in `.env`: `MIN_CLUSTER_TRACES`, `CLUSTER_MEAN_DISTANCE_M`, `CLUSTER_OVERLAP_FRACTION`, `CLUSTER_MIDPOINT_MAX_M`.

## JOSM User Experience Goals
When a user opens `clusters/near_thao_dien_park_footpath_01/` they should immediately understand:
- What this path is called and why it matters
- Exactly which of their runs cover it
- What OSM already knows in the immediate 50m surroundings
- Which GPX traces to load as background/reference

The `cluster_meta.json` and directory structure should support this mental model perfectly.

## Vietnamese / HCMC Specifics
- POI names often contain Vietnamese diacritics and words like "Phường", "Quận", "Đường", "Hẻm", "Công viên", "Chùa", "Nhà thờ".
- Many "footpaths" are actually narrow motorbike-accessible alleys (`residential` + `access=private` or just un-tagged).
- GPS accuracy in dense urban + tree cover can be 5-15m off. The 50m buffer + clustering tolerance accounts for this.
- Common useful landmarks for naming: coffee shops (very dense in Saigon), pho places, parks, pagodas, apartment entrances, canal paths, "shortcut to [major road]".

## When in Doubt
- Ask: "Will this make the JOSM mapping session faster and more accurate for a tired runner who just got home from a 10km run?"
- Prefer shipping a useful 80% solution today over a perfect 100% solution in three weeks.
- If a step is slow, add clear progress + ETA and a `--limit` flag for testing.

## Maintenance
- When adding a new CLI command, also add the corresponding `make` target and document it in `usage.md`.
- Bump version in `pyproject.toml` for any user-visible improvement.
- Keep `samples/` representative of real-world messiness (not just perfect straight lines).

This project is a labor of love for the OSM + running community in Vietnam. Treat the data and the future mapper's time with respect.
