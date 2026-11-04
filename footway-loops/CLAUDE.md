# CLAUDE.md

## What this is

Finds self-transcendence running loops (default 883 m, the Self-Transcendence 3100 lap) on OSM footpaths within a radius of a point, and exports them as one KML plus a GPX per loop.

## Key files

- `scripts/find_loops.py` — whole pipeline: osmium clip + footpath filter, graph build, chain contraction + bounded beam cycle search, KML/GPX export
- `docs/algorithm.md` — how the cycle search works
- `tests/test_find_loops.py` — cycle search and palette on synthetic grids

## How to run

- `make run LOCATION=<lat>,<lon>` — fetches the country extract via dotfiles' `osm-country.mk`, then runs the script; `RADIUS`, `TARGET`, `EPSILON` override defaults
- `make test`

## Conventions / gotchas

- Output lives outside the repo in `~/Documents/data/footway-loops` (`DATA_DIR`), one folder per `<lat>_<lon>_<radius>m`; nothing is written into the project.
- The beam keeps 24 partial paths per junction in each 40 m band. A dense street grid returns a sample of the loops in the window. Loops that cross a vehicle road are dropped, and so are loops with two corners of 60° or more under 15 m apart. The smoothest 10 of what remains are kept: fewer turns (a heading change of at least 30°), then park loops, then closer to the target length. A sidewalk beside a road stays; a bridge or tunnel on another level stays.
- Nodes outside the radius are dropped, so footpaths crossing the circle edge show up as skipped segments.
