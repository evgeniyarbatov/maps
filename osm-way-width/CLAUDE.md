# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Estimates the real-world width of a single OSM way by comparing it against multiple GPS polylines (from Strava running activities) that cross it: project each polyline point onto the way, compute perpendicular offsets, and derive width from the offset distribution (overall and per 10 m segment).

## Key files

- `scripts/extract_way_segment.py` — pulls one way (by ID + start/end node) out of a clipped `.osm` file
- `scripts/estimate_way_width.py` — aggregate width estimate (p95 - p5 of perpendicular distances) across all polylines
- `scripts/segment_way_width.py` — per-segment width + plot (`width_segments.csv`, `width_segments.png`)
- `scripts/way_width_utils.py` — shared projection/distance/outlier-filtering logic
- `data/polylines/` — checked-in encoded (Google polyline format) GPS traces, one JSON file per activity
- `osm/times-city.poly` — checked-in boundary polygon for the shipped example

## How to run

- `make country` — one-time download of the country OSM PBF (needs `evgeniyarbatov/dotfiles` helper, or fetch manually per the Makefile's error message)
- `make run` — entry point: `area` (clip OSM to boundary) -> `way` (extract target way) -> `segments` (compute + plot per-segment widths)
- `make width` — aggregate width estimate only (skips segmentation/plot)
- `make test` — unit tests (`unittest discover -s tests`)

## Conventions / gotchas

- `WAY_ID`, `WAY_START_NODE`, `WAY_END_NODE`, `BOUNDARY_POLY`, `OSM_URL` in the Makefile define the target way/area; edit them to point at a different way (see README "With Your Own Data").
- Outliers are removed via 3*MAD (median absolute deviation) from the median signed perpendicular distance before estimating width.
- Generated OSM extracts and `segments` outputs go to `$(DATA_DIR)` (default `~/data/osm-way-width/`), outside the repo; override with `DATA_ROOT=` or `DATA_DIR=`.
