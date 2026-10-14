# AGENTS.md

Each top-level folder is an independent project. Work inside one folder; `cd <folder> && make help` lists its targets. If a folder has its own `CLAUDE.md`, read it first.

## Hub setup

- Python folders share one uv workspace: `uv sync --all-packages` at the root (or `make setup` in the folder).
- Folders marked `osm-country` include `$(HOME)/gitRepo/dotfiles/make/osm-country.mk`; clone `dotfiles` to `~/gitRepo/dotfiles` first. The country extract is cached in `~/.cache/osm`; don't download Geofabrik inside a project.
- OSM extracts, personal GPX and generated outputs are gitignored, and several folders write outside the repo (`DATA_ROOT`, default `~/Documents/data` or `~/data`).

## Needs

| Tag | Meaning |
|---|---|
| `osm-country` | `dotfiles` cloned at `~/gitRepo/dotfiles` |
| `osrm` | Local OSRM in Docker |
| `overpass` | Local Overpass API in Docker |
| `ollama` | Ollama on `localhost:11434` with the model named in the folder's config |
| `gpx` | My own GPX files, placed by hand or via `GPX_DIR` |
| `activity-data` | Tracks fetched from the activity-data repo, configured in `.env` |

## Folders

| Folder | What it does | Run | Needs |
|---|---|---|---|
| `gpx-courses` | Merges several GPX tracks into one clean course using OSM and OSRM | `make run GPX_DIR=<dir> NAME=<course>` | `osm-country`, `osrm`, `overpass` |
| `gpx-osm-missing-paths` | Clusters traces to find footpaths missing from OSM; builds JOSM bundles | `make run` | `osm-country`, `activity-data` (copy `env.example` to `.env`) |
| `osm-way-width` | Estimates OSM way width from many run polylines | `make run` | `osm-country`, Strava polylines in `DATA_DIR` |
| `osm-waypoints` | OSM POIs along GPX walks, curated by an LLM, exported as Garmin waypoints | `make run` | `osm-country`, `ollama`, `gpx` |
| `vibe-mapping` | Per-cell urban signals and an LLM "vibe" of a place from OSM features | `make run` | `osm-country`, `ollama` |
| `gpx-map` | Renders GPX segments on a map; notebooks and video export | `make run` (npm dev server on :3000) | `gpx` in `DATA_DIR`, npm |
| `photo-map` | Local web app finding geotagged photos on a map | `make extract-photos INPUT_DIR=<photos>`, then `make run` | photos from photo-archive, npm |
| `geo-stack` | Shared OSRM (foot, bicycle) for Hanoi, HCMC, Singapore on 7011–7033 and Overpass on 7080 | `make setup run` | `osm-country`, Docker |

## Cautions

- `gpx-courses`: `make clean-data` and `make clean-data-gpx` delete generated data.
- `gpx-courses` binds OSRM on port 6000, the same port as OSRM stacks in route-lab and gpx-tools.
