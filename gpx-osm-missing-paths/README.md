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
# 1. Clone / create the project
git clone ... gpx-osm-missing-paths
cd gpx-osm-missing-paths

# 2. Setup (uv recommended)
make setup
# or: uv sync --all-extras && cp .env.example .env

# 3. Edit .env
# Set OSM_PBF_PATH to your local extract (download from geofabrik.de or cut with osmium)
# Put your raw .gpx files into ./gpx/ (this folder is gitignored)

# 4. Run the full pipeline
make pipeline

# 5. Open results
open clusters/          # or explorer clusters/
# For any cluster:
#   - Drag the .osm into JOSM
#   - Drag the .gpx files from its gpx/ subfolder as reference layers
#   - Draw the missing path where your traces show it should be
```

## Pipeline Stages

| Step | Command          | What it does |
|------|------------------|--------------|
| 1    | `make process`   | Parse every GPX, clean points, simplify, filter short segments, produce `output/segments.*` |
| 2    | `make cluster`   | Deduplicate + cluster segments that physically overlap (HDBSCAN + overlap graph). Creates representative lines per cluster |
| 3    | `make name`      | Load POIs from your OSM extract once, then for every cluster find nearby landmarks and generate a beautiful human-readable name + slug |
| 4+5  | `make extract`   | For each cluster: compute 50m buffer → `osmium extract` a tiny focused `.osm` → bundle with all its GPX files + `cluster_meta.json` |
| All  | `make pipeline`  | Runs 1→4 in order with nice progress |

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
- `uv` (or pip, but uv is strongly preferred)
- `osmium-tool` (for fast local OSM extracts and POI preparation)
  - macOS: `brew install osmium-tool`
  - Ubuntu/Debian: `apt install osmium-tool`
- Docker (optional, only if you want to experiment with local OSRM map-matching)
- A regional OSM PBF extract (e.g. `vietnam-latest.osm.pbf` or a city cut). Place it somewhere and point `OSM_PBF_PATH` at it.

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
