# osm-waypoints

Extract OpenStreetMap points of interest along GPX walking tracks, curate them with a local LLM, and export Garmin-ready waypoints with distinct icons and short labels.

Built for planning on-foot outings — forest paths, village strolls, scenic walks, not just mountain hiking. The goal is a broad list of interesting places near your routes; trimming on the Garmin is easy.

## Prerequisites

- **Python 3.10+** (system install)
- **macOS** with [Homebrew](https://brew.sh) for **[osmium-tool](https://osmcode.org/osmium-tool/)** and **[Ollama](https://ollama.com/)** — listed in `Brewfile`

## Installation

Install system and Python dependencies:

```bash
make install
```

This runs `brew bundle` from the `Brewfile` (osmium-tool, ollama), creates a venv at `.venv`, and installs packages from `requirements.txt`.

The default Ollama model (`mistral-nemo`) is pulled automatically on the first `validate-pois` or `describe-pois` run.

## Quick start

```bash
make install
make all GPX_DIR=/path/to/your/gpx/files
```

Default `GPX_DIR` is `/Users/arbatov/Documents/gpx/nui-dinh`.

## Pipeline

Each step is a separate Makefile target.

| Step | Command | Output |
|------|---------|--------|
| 1. OSM extract | `make extract-osm` | `osm/extract.osm` — convex hull of all GPX tracks + 250 m buffer |
| 2. POI extraction | `make extract-pois` | `data/pois.json` — viewpoints, peaks, temples, churches, historic sites, museums, etc. |
| 3. LLM validation | `make validate-pois` | `data/pois_validated.json` — filters obvious OSM misclassifications |
| 4. LLM descriptions | `make describe-pois` | updates `data/pois_validated.json` — short noun-phrase labels from OSM tags |
| 5. Map render | `make render-map` | `data/waypoints.png` — high-res contextily basemap |
| 6. GPX export | `make export-gpx` | `data/waypoints.gpx` — Garmin waypoints with per-type icons and ASCII names |

### Run step by step

```bash
make install          # brew deps + Python venv
make country          # download vietnam-latest.osm.pbf (~310 MB, once)
make extract-osm
make extract-pois
make validate-pois
make describe-pois
make render-map
make export-gpx
```

## What you get

- **Tight extract** — buffered convex hull polygon around your tracks (`osm/extract-polygon.geojson`), not a loose rectangle
- **Forgiving POI filter** — keeps anything interesting on a walk; drops shops, parking, and tagging mistakes
- **Short descriptions** — 3–8 word phrases like `Buddhist temple` or `491 m peak`, no action verbs
- **Garmin-friendly GPX** — distinct `<sym>` icons per POI type, Vietnamese transliterated to ASCII
- **Sensible names** — uses `name:en` when available; unnamed POIs get their OSM type (e.g. `Viewpoint`)

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `GPX_DIR` | `/Users/arbatov/Documents/gpx/nui-dinh` | Input GPX directory |
| `BUFFER_KM` | `0.25` | Buffer around track hull in km (250 m) |
| `OLLAMA_MODEL` | `mistral-nemo` | Ollama model for validation and descriptions |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama API endpoint |
| `MAP_DPI` | `300` | Map image resolution |

```bash
make all GPX_DIR=~/Documents/gpx/my-trail BUFFER_KM=0.5
```

## Outputs

```
osm/
  vietnam-latest.osm.pbf    # country PBF (cached)
  extract-polygon.geojson   # buffered convex hull
  extract.osm               # regional OSM extract

data/
  pois.json                 # raw POIs
  pois_validated.json       # filtered POIs + short descriptions
  waypoints.png             # map preview
  waypoints.gpx             # upload to Garmin
```

## Clean up

```bash
make clean
```

Removes generated extracts and data files; keeps the downloaded country PBF.
