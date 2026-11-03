# CLAUDE.md

## What this is

Finds self-transcendence running loops (default 883 m, the Self-Transcendence 3100 lap) on OSM footpaths within a radius of a point, and exports them as one KML plus a GPX per loop.

## Key files

- `scripts/find_loops.py` — whole pipeline: osmium clip + footpath filter, graph build, chain contraction + meet-in-the-middle cycle search, KML/GPX export
- `docs/algorithm.md` — how the cycle search works
- `tests/test_find_loops.py` — cycle search and palette on synthetic grids

## How to run

- `make run LOCATION=<lat>,<lon>` — fetches the country extract via dotfiles' `osm-country.mk`, then runs the script; `RADIUS`, `TARGET`, `EPSILON` override defaults
- `make test`

## Conventions / gotchas

- Output lives outside the repo in `~/Documents/data/footway-loops` (`DATA_DIR`), one folder per `<lat>_<lon>_<radius>m`; nothing is written into the project.
- All candidate cycles are enumerated and held in memory before ranking, so large `RADIUS`/`EPSILON` cost memory.
- Nodes outside the radius are dropped, so footpaths crossing the circle edge show up as skipped segments.
