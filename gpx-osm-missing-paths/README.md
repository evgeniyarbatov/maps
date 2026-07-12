# gpx-osm-missing-paths

**Turn your personal running/walking GPX traces into precise, JOSM-ready contributions to OpenStreetMap.**

Identify footpaths, alleys, stairways, and informal routes that are missing from OSM, cluster all your traces that cover the same physical path, automatically name them using nearby landmarks, and export tiny focused `.osm` extracts + the exact GPX files you need — all locally, with zero external API calls after setup.

Perfect for runners, walkers, and mappers in places like Ho Chi Minh City (Saigon), Hanoi, or any city where you have a local OSM extract.

## Why This Exists

You run the same new alley or park shortcut 12 times. Each GPX is slightly different due to GPS noise. Manually hunting through dozens of files in JOSM is painful. This pipeline:

- Groups all traces that belong to the **same physical path** into one cluster
- Gives the cluster a human name like *"Footpath behind Thao Dien Park connecting to Nguyen Van Huong"*
- Hands you a ready-to-open JOSM bundle: small `.osm` of the 50m surroundings + every relevant GPX file
- Lets you focus on the fun part: drawing beautiful, accurate missing geometry in JOSM

## Quickstart

```bash
# 1. Clone
git clone ... gpx-osm-missing-paths
cd gpx-osm-missing-paths

# 2. Setup (uv)
make setup
cp env.example .env   # optional; defaults target HCMC + Vietnam cache

# 3. OSM (shared cache — do not download Geofabrik inside this repo)
# Country PBF: ~/.cache/osm/vietnam-latest.osm.pbf
# Maintained by dotfiles launchd com.arbatov.fetch-osm (weekly) or:
make country          # calls ~/gitRepo/dotfiles/bin/fetch-osm
make city             # clip to osm/hcm.poly → osm/hcm.osm.pbf

# 4. Drop raw .gpx into ./gpx/ (gitignored)

# 5. Full pipeline (city clip + process + cluster + missing filter + name + extract)
make pipeline

# 6. Open results
open clusters/
# For any cluster:
#   - Drag the .osm into JOSM
#   - Drag the .gpx files from its gpx/ subfolder as reference layers
#   - Draw the missing path where your traces show it should be
```

### Other city / country

```bash
# Another city (same country PBF) — add osm/hanoi.poly first
make city BOUNDARY_POLYGON=osm/hanoi.poly
make pipeline BOUNDARY_POLYGON=osm/hanoi.poly

# Another country (shared cache basename must match Geofabrik file)
make country URL=https://download.geofabrik.de/asia/thailand-latest.osm.pbf
```

## Pipeline Stages

| Step | Command | What it does |
|------|---------|--------------|
| 0a | `make country` | Ensure country PBF in `~/.cache/osm` via **dotfiles fetch-osm** (no parallel download flow) |
| 0b | `make city` | Clip country PBF with `BOUNDARY_POLYGON` (default `osm/hcm.poly`) → `osm/<city>.osm.pbf` |
| 1 | `make process` | Parse every GPX, clean, simplify → `output/segments.*` |
| 2 | `make cluster` | Cluster overlapping segments → representative lines |
| 3 | `make filter-missing` | Keep only clusters poorly covered by OSM ways |
| 4 | `make name` | POI-based human names for missing clusters |
| 5 | `make extract` | 50m `.osm` + GPX bundle + `cluster_meta.json` (`num_gpx_traces`, `avg_length_m`) |
| All | `make pipeline` | `city` then 1→5 |

## Output Structure

```
clusters/
└── footpath_behind_thao_dien_park_connecting_to_nguyen_van_huong/
    ├── footpath_behind_thao_dien_park_connecting_to_nguyen_van_huong.osm   # JOSM-ready (everything in 50m buffer)
    ├── cluster_meta.json
    ├── representative.geojson
    └── gpx/
        ├── morning_run_2025-06-12.gpx
        ├── evening_loop_2025-06-18.gpx
        └── ...
```

Open the `.osm` in JOSM, load the GPX files from the subfolder, and you have perfect context + reference data.

## Requirements

- Python 3.12+
- `uv` (strongly preferred)
- `osmium-tool` and `osmconvert` (city clip + per-cluster extracts)
  - macOS: `brew install osmium-tool osmctools` (or equivalent providing `osmconvert`)
  - Ubuntu/Debian: `apt install osmium-tool osmctools`
- Shared country OSM cache from **dotfiles** (`com.arbatov.fetch-osm` → `~/.cache/osm/…`)
- Docker (optional, local OSRM only)

## Tuning for Your City / Data

Edit `.env`:

- `MIN_SEGMENT_LENGTH_M` — ignore GPS noise / very short detours
- `HDBSCAN_MIN_CLUSTER_SIZE` — how many traces needed before something becomes a "cluster" (raise for noisy data, lower if you have few repeats)
- `CLUSTER_BUFFER_M` / `POI_SEARCH_RADIUS_M` — usually 50m is perfect for urban footpaths
- `SIMPLIFY_TOLERANCE_M` — 3-5m works well for running GPS

See `docs/usage.md` for full parameter reference and recommended values for HCMC dense alleys vs. park trails.

## Advanced / Optional

- **Local OSRM**: See `docs/osrm-setup.md` for cutting a small HCMC bbox and building a routing graph. Then you can experiment with map-matching to further clean traces or detect "off-OSM" segments automatically.
- **Incremental runs**: The pipeline is designed to be re-runnable. Add new GPX files to `gpx/` and re-run `make pipeline`. (Full reprocess is fast enough for personal collections of a few thousand files.)
- **Visualization**: `make viz` (if implemented) produces a folium HTML overview of all clusters.

## Project Status

This project was scaffolded with a comprehensive spec. The core implementation (processor, clusterer, namer, extractor + CLI + docs) is intended to be generated/completed by feeding `docs/claude-code-prompt.md` into Claude (or Cursor/Windsurf).

If you are reading this after generation, the pipeline should be fully functional on sample data and ready for your real GPX collection.

## Contributing & Philosophy

- Issues and PRs that improve JOSM mapping experience or clustering quality for real-world urban running data are very welcome.
- This is a tool for **embodied mapping** — getting out, running/walking every street, and giving that data back to the commons as high-quality OSM geometry.
- Built with ❤️ for the Saigon running + OSM community (and anyone else who wants their traces to improve the map).

## Related

- [JOSM](https://josm.openstreetmap.de/)
- [osmium-tool](https://osmcode.org/osmium-tool/)
- User's running + mapping notes often live at arbatov.uk or OSM diaries

---

**Ready to map the missing paths?** Drop your GPX files and run `make pipeline`.
