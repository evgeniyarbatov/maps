# osm-waypoints

The idea came to my mind when planning a Nui Dinh trip. Take an OSM extract within a given area and list all POIs in it. Save as a GPX file that I can upload to Garmin. Deleting waypoints is easy — I want to get a comprehensive list of what is available. Asking an LLM works, but this is a self-hosted option.

## Prerequisites

- **Python 3.10+**
- **[osmium-tool](https://osmcode.org/osmium-tool/)** — used to cut a regional extract from the country PBF
- **[Ollama](https://ollama.com/)** — for the POI validation step (local LLM)

```bash
brew install osmium-tool ollama
ollama pull mistral-nemo
```

## Quick start

Point `GPX_DIR` at a folder of hiking track GPX files, then run the full pipeline:

```bash
make all GPX_DIR=/path/to/your/gpx/files
```

Default `GPX_DIR` is `/Users/arbatov/Documents/gpx/nui-dinh`.

## Pipeline steps

Each step is a separate Makefile target. Run them individually or chain with `make all`.

| Step | Command | Output |
|------|---------|--------|
| 1. OSM extract | `make extract-osm` | `osm/extract.osm` — 250 m buffer around all GPX tracks |
| 2. POI extraction | `make extract-pois` | `data/pois.json` — viewpoints, attractions, temples, churches, historic sites, peaks, etc. |
| 3. LLM validation | `make validate-pois` | `data/pois_validated.json` — filters OSM misclassifications via Ollama |
| 4. Map render | `make render-map` | `data/waypoints.png` — high-res map with contextily basemap |
| 5. GPX export | `make export-gpx` | `data/waypoints.gpx` — Garmin-compatible waypoints |

Step 3 runs after POI extraction. Steps 4 and 5 use the validated POI list.

### Run individual steps

```bash
make install          # create venv and install Python deps
make country          # download vietnam-latest.osm.pbf (~310 MB, cached)
make extract-osm      # step 1
make extract-pois     # step 2 (depends on step 1)
make validate-pois    # step 3 (depends on step 2)
make render-map       # step 4 (depends on step 3)
make export-gpx       # step 5 (depends on step 3)
```

## Configuration

Override defaults via Make variables or environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `GPX_DIR` | `/Users/arbatov/Documents/gpx/nui-dinh` | Directory of input GPX files |
| `BUFFER_KM` | `0.25` | Buffer distance around tracks in km (default 250 m) |
| `OLLAMA_MODEL` | `mistral-nemo` | Ollama model for POI validation |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama API endpoint |
| `MAP_DPI` | `300` | Resolution of the rendered map image |

Example with a different area and buffer:

```bash
make all GPX_DIR=~/Documents/gpx/my-trail BUFFER_KM=2
```

## Outputs

```
osm/
  vietnam-latest.osm.pbf   # country extract (downloaded once)
  extract.osm              # buffered area extract

data/
  pois.json                # raw POIs from OSM
  pois_validated.json      # POIs after LLM filtering
  waypoints.png            # map preview
  waypoints.gpx            # upload to Garmin
```

## Clean up generated files

```bash
make clean
```

This removes generated extracts and data files but keeps the downloaded country PBF.