# gpx-osm-missing-paths

[![tests](https://github.com/evgeniyarbatov/gpx-osm-missing-paths/actions/workflows/tests.yml/badge.svg)](https://github.com/evgeniyarbatov/gpx-osm-missing-paths/actions/workflows/tests.yml)

Find footpaths, alleys and shortcuts you keep running that are missing from OpenStreetMap, and get a JOSM-ready bundle for each one. Fully local after the OSM extract is cached.

<img width="2899" height="1493" alt="josm" src="https://github.com/user-attachments/assets/5abbff1c-e685-4fa4-8e80-fe345154dd93" />

Traces of the same physical path are clustered, checked against existing OSM ways, named after nearby landmarks, and exported as a small `.osm` of the 50m surroundings plus every GPX that covers it.

## Quickstart

Requires Python 3.11+, [`uv`](https://docs.astral.sh/uv/) and `osmium-tool`.

```bash
git clone https://github.com/evgeniyarbatov/maps.git
cd gpx-osm-missing-paths
make setup
cp env.example .env                # optional; defaults target HCMC

make country                       # Vietnam PBF → ~/.cache/osm (prints manual download URL if unavailable)
make city                          # clip to osm/hcm.poly

# Drop .gpx files into ~/Documents/data/gpx-osm-missing-paths/gpx/, or fetch from a parquet track repo:
make gpx LAT=<lat> LON=<lon> RADIUS_KM=5   # filter is optional

make pipeline
open ~/Documents/data/gpx-osm-missing-paths/clusters/
```

In JOSM, open a cluster's `.osm`, add its `gpx/*.gpx` as reference layers, and draw the path.

Another city: add `osm/<city>.poly`, then `make pipeline BOUNDARY_POLYGON=osm/<city>.poly`. Another country: `make country URL=<geofabrik .osm.pbf URL>`.

## Output

```
clusters/
└── footpath_near_thao_dien_park_off_nguyen_van_huong/
    ├── footpath_near_thao_dien_park_off_nguyen_van_huong.osm
    ├── cluster_meta.json
    ├── representative.geojson
    └── gpx/
```

Bundles are written only for clusters seen in at least `MIN_CLUSTER_TRACES` GPX files (default 2) with low OSM coverage.

## Docs

- [Usage](docs/usage.md) — commands, `.env` knobs, testing against `samples/`
- [Architecture](docs/architecture.md) — pipeline stages and data flow
- [Missing-way detection](docs/missing-ways.md) — the coverage check
- [Data model](docs/data-model.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Roadmap](ROADMAP.md)
