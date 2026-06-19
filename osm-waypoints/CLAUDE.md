# CLAUDE.md

Guide for AI assistants working in this repository.

## Project purpose

Extract points of interest from OpenStreetMap along GPX walking tracks, filter obvious OSM misclassifications with a local Ollama model, render a preview map, and export Garmin-compatible GPX waypoints.

Primary use case: planning on-foot outings (not limited to mountain hiking) and loading curated waypoints onto a Garmin device.

## Pipeline

Five Makefile steps, run in order:

1. `extract-osm` — convex hull of all GPX points, buffered by `BUFFER_KM`, written to `osm/extract-polygon.geojson`, then cut from country PBF via `osmium extract -p`
2. `extract-pois` — parse `osm/extract.osm`, match POI tag rules, write `data/pois.json`
3. `validate-pois` — Ollama filters each POI, write `data/pois_validated.json`
4. `render-map` — plot validated POIs on a contextily basemap, write `data/waypoints.png`
5. `export-gpx` — write `data/waypoints.gpx` with Garmin symbols and ASCII names

Run everything: `make all GPX_DIR=/path/to/gpx`

## Key files

| File | Role |
|------|------|
| `Makefile` | Pipeline orchestration and config defaults |
| `scripts/config.py` | Paths and env-backed settings |
| `scripts/gpx_utils.py` | Load GPX points; build buffered convex hull polygon |
| `scripts/extract_osm.py` | Write polygon GeoJSON; call osmium |
| `scripts/poi_rules.py` | OSM tag matching; POI display names |
| `scripts/extract_pois.py` | OSM XML → JSON waypoints |
| `scripts/validate_pois.py` | Ollama validation prompt and API calls |
| `scripts/render_map.py` | High-res contextily map |
| `scripts/garmin_symbols.py` | OSM category → Garmin `<sym>` mapping |
| `scripts/text_utils.py` | Vietnamese/Unicode → ASCII via `unidecode` |
| `scripts/export_gpx.py` | Garmin GPX output |

## External dependencies

- **Python 3.10+** with venv at `.venv`
- **osmium-tool** — polygon extract from Geofabrik country PBF
- **Ollama** — default model `mistral-nemo` at `http://localhost:11434`

Scripts are run from `scripts/` by the Makefile (`cd scripts && python script.py`). Imports are flat (`from config import ...`), not package-relative.

## Configuration

Environment variables (also exported by Makefile):

| Variable | Default | Notes |
|----------|---------|-------|
| `GPX_DIR` | `/Users/arbatov/Documents/gpx/nui-dinh` | All `*.gpx` in directory are used |
| `BUFFER_KM` | `0.25` | 250 m buffer around convex hull |
| `OLLAMA_MODEL` | `mistral-nemo` | Pulled automatically if missing |
| `OLLAMA_URL` | `http://localhost:11434` | |
| `MAP_DPI` | `300` | |

## Implementation notes

### OSM extract geometry

- Collect all track/route/waypoint coordinates from GPX files.
- Build convex hull in UTM, buffer once, export as GeoJSON.
- Do **not** buffer a `MultiPoint` of every GPX coordinate — that is very slow on large tracks.
- A rectangular bbox alone is not desired; use the convex hull polygon.

### POI naming

- Prefer `name:en`, then `name`, `alt_name`, `official_name`.
- If no name exists, use the OSM category label (e.g. `Viewpoint`, `Monument`) — never `"Unnamed POI"`.

### Ollama validation

- Prompt is intentionally forgiving: keep anything interesting on a casual walk.
- Only reject clearly non-walk-relevant POIs (shops, parking, obvious tagging errors).
- Default bias: when unsure, keep the POI.

### Garmin GPX export

- Use distinct Garmin `<sym>` values per POI type (`garmin_symbols.py`).
- Transliterate all waypoint text to ASCII for Garmin compatibility (`text_utils.py`).
- Symbols must match Garmin icon names (e.g. `Scenic Area`, `Summit`, `Church`, `Building`).

### Gitignored outputs

- `osm/*` except `osm/.gitkeep` (country PBF and extracts stay local)
- `data/*` except `data/.gitkeep` (generated JSON, PNG, GPX)

## Development conventions

- Keep each pipeline step as a separate script and Makefile target.
- Put shared paths in `config.py`; put domain logic in focused modules.
- Match existing style: minimal comments, no drive-by refactors, Python stdlib + small deps.
- When changing POI rules, update both `poi_rules.py` and `garmin_symbols.py` if symbol mapping is affected.
- After changing extract/POI logic, downstream steps need re-running (`extract-pois` onward).

## Common commands

```bash
make install
make extract-osm GPX_DIR=/path/to/gpx
make extract-pois
make validate-pois
make export-gpx
make clean
```

## Do not

- Commit generated files in `osm/` or `data/` (except `.gitkeep`).
- Reintroduce slow geometry operations over full GPX point sets.
- Use non-Garmin symbol names in GPX `<sym>` tags without checking `garmin_symbols.py`.
- Make the Ollama prompt overly strict — the user wants a broad, walk-friendly POI list.