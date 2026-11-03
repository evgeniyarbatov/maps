# CLAUDE.md

## What this is

Finds self-transcendence running loops (default 883 m, the Self-Transcendence 3100 lap) on OSM footpaths within a radius of a point, and exports them as one KML plus a GPX per loop.

## Key files

- `scripts/find_loops.py` — whole pipeline: osmium clip + footpath filter, graph build, bounded-DFS cycle search, KML/GPX export
- `tests/test_find_loops.py` — cycle search and palette on synthetic grids

## How to run

- `make run LOCATION=<lat>,<lon>` — fetches the country extract via dotfiles' `osm-country.mk`, then runs the script; `RADIUS`, `TARGET`, `EPSILON` override defaults
- `make test`

## Conventions / gotchas

- Output lives in `data/` inside the project (gitignored), one folder per `<lat>_<lon>_<radius>m`.
- The search stops at `MAX_LOOPS` before sorting, so "closest to target" is among the loops found first, not globally.
- Nodes outside the radius are dropped, so footpaths crossing the circle edge show up as skipped segments.
