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

## Never Do
- Commit anything inside `gpx/`, `clusters/`, `output/`, or large `.osm`/`.pbf` files.
- Rely on internet/Overpass after initial setup. Everything must work with a local PBF + `osmium`.
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
- `src/gpx_osm_pipeline/models.py` — Single source of truth for `GPXSegment`, `Cluster`, `POI`, `Config`.
- `config.py` — Loads `.env` + defaults into Pydantic `Settings`. All tunable params live here.
- `gpx_processor.py` — The only place that touches `gpxpy`. Produces clean segments.
- `clusterer.py` — Contains the documented clustering heuristic. If you change the algorithm, update the big comment block and architecture doc.
- `namer.py` — POI loading (once), spatial queries, name generation logic. Keep the ranking rules clear.
- `osm_extractor.py` — All `osmium` subprocess calls + buffer math + bundle writing. Atomic writes preferred.
- `cli.py` — Typer commands only. Thin orchestration + pretty printing. Business logic stays in modules.
- `utils.py` — Small pure helpers (haversine, bearing, slugify, UTM zone guess for Vietnam, etc.).

## Clustering Heuristic Notes (Important Context)
The current implementation uses [describe the hybrid HDBSCAN + overlap graph or whatever was chosen]. 
It intentionally errs on the side of **slightly over-clustering** (user can split in JOSM) rather than leaving 15 almost-identical traces as separate clusters.
If you need to adjust sensitivity, the primary knobs are in `.env`: `HDBSCAN_MIN_CLUSTER_SIZE`, `CLUSTER_BUFFER_M`, and the overlap % / Hausdorff thresholds inside `clusterer.py`.

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
