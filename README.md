# maps

Open tools that join my GPS traces with OpenStreetMap: merge tracks into courses, find footpaths missing from OSM, measure how wide a way really is, pull waypoints, and put GPX tracks and geotagged photos on a map.

## Projects

**GPX + OSM**

| Folder | What it does | Run |
|---|---|---|
| [gpx-courses/](gpx-courses) | Merges multiple GPX tracks into one course using OSM and OSRM | `make extract compress` |
| [gpx-osm-missing-paths/](gpx-osm-missing-paths) | Clusters GPX traces to find footpaths missing from OSM and builds JOSM-ready bundles | `make city gpx process cluster` |
| [osm-way-width/](osm-way-width) | Estimates the width of OSM ways from many polylines | `make area way width` |
| [osm-waypoints/](osm-waypoints) | Extracts, validates and describes points of interest from OSM as waypoints | `make extract-osm extract-pois` |
| [vibe-mapping/](vibe-mapping) | Uses OSM features and a local LLM to learn the vibe of a place | `make area points` |

**On the map**

| Folder | What it does | Run |
|---|---|---|
| [gpx-map/](gpx-map) | Displays GPX track segments on a map, with notebooks and video export | `make run` |
| [photo-map/](photo-map) | Finds geotagged photos on a map | `make extract-photos run` |

## Getting started

Each folder is a standalone project with its own Makefile; Python folders use uv. OSM extracts and personal GPX files aren't committed: each folder's README says where to put them. `gpx-courses` needs Docker for local OSRM.

Related live sites are kept as their own repos: [gpx-editor](https://github.com/evgeniyarbatov/gpx-editor) and [singapore-streets](https://github.com/evgeniyarbatov/singapore-streets).
