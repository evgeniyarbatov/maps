# Architecture Overview

## High-Level Data Flow

```
gpx/*.gpx
   │
   ▼ gpx_processor.py
cleaned GPXSegment objects (LineString + metadata)
   │
   ▼ clusterer.py
Cluster objects (grouped segments + representative_line)
   │
   ▼ namer.py  (uses pre-built pois layer)
named Cluster objects (human_name, slug, nearby_pois)
   │
   ▼ osm_extractor.py
clusters/{slug}/
   ├── {slug}.osm          (osmium extract, 50m buffer)
   ├── cluster_meta.json
   ├── representative.geojson
   └── gpx/ (copies of relevant raw files)
```

## Core Components

### 1. Models (`models.py`)
Pydantic v2 frozen models:
- `GPXSegment`: one continuous `<trkseg>` after cleaning
- `Cluster`: group of segments that represent one physical path
- `POI`: landmark from OSM used for naming
- `PipelineConfig` / `Settings`: all tunable parameters + paths

### 2. GPX Processing
- Single responsibility: turn messy real-world GPX into clean, simplified, validated LineStrings in EPSG:4326.
- Heavy use of `shapely` for geometry ops, `gpxpy` only for parsing.
- Projections to local UTM (Vietnam zone 48N/49N) only when meter-accurate buffering or length is needed.

### 3. Clustering Strategy (see `clusterer.py` for exact implementation)
Hybrid approach chosen for balance of quality and performance on personal-scale data (hundreds to low thousands of segments):

1. **Rough spatial bucketing** (H3 or simple grid on midpoints) to avoid O(n²).
2. **Within-bucket proximity graph**:
   - Buffer segments by ~10-12m
   - Calculate overlap ratio + Hausdorff distance
   - Connect if they "belong together" (high overlap or very close + similar direction)
3. **Connected components** → `cluster_id`
4. Per cluster: pick longest segment as canonical or compute simple union/skeleton for representative geometry.

This naturally handles GPS noise, slight parallel runs, and different directions on the same path.

**Key insight**: We cluster *segments*, not raw points. This preserves the path shape while grouping evidence for the same missing OSM way.

### 4. POI-based Naming
- One-time expensive step: `osmium export` filtered to named features with useful tags → `output/pois.parquet` (or geojson).
- Fast per-cluster spatial queries using `geopandas.sjoin` or `shapely` STRtree on the 50m buffered representative line.
- Ranking heuristic favors:
  - Closer POIs
  - "Important" categories (park, school, pagoda, major cafe)
  - Named streets/highways for context ("along ...")
- Slug generation produces filesystem-safe, readable directory names.

### 5. OSM Extraction
- Pure `osmium extract --bbox` (or polygon) per cluster.
- 50m buffer chosen because:
  - Covers typical GPS error + path width
  - Keeps `.osm` files tiny (usually < 500KB even in dense areas)
  - Gives JOSM enough context (buildings, crossing ways, nearby tags) without overwhelming the editor.

## Why This Stack?

| Concern              | Choice                     | Reason |
|----------------------|----------------------------|--------|
| Package management   | uv                         | Blazing fast, modern, reproducible |
| CLI                    | Typer + Rich               | Beautiful, discoverable, type-safe |
| Geospatial           | geopandas + shapely        | Mature, powerful, great ecosystem |
| Clustering           | hdbscan + custom graph     | Density-based + domain-specific rules |
| OSM data             | osmium-tool (CLI)          | Extremely fast, low memory, standard in OSM community |
| Config               | pydantic + .env            | Validation + great DX |
| Optional routing     | OSRM in Docker             | Industry standard, can be used for advanced matching later |

## Non-Goals (for v1)

- Perfect automatic centerline extraction from many noisy traces (very hard; JOSM human + GPX reference is better)
- Full map-matching / conflation back into OSM (out of scope; this feeds JOSM)
- Web UI or QGIS plugin (CLI + files is sufficient and portable)
- Handling of hundreds of thousands of segments without chunking (personal use case first)

## Future Nice-to-Haves (documented but not required)

- Optional OSRM match step to flag "likely missing" segments automatically
- Strava/Garmin API import (or folder watch)
- Automatic creation of JOSM session files (.jos) or layer presets
- Integration with OSMCha or other quality tools

See `docs/usage.md` for operational details and `CLAUDE.md` for implementation guidelines.
