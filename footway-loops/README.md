# Footway Loops

Finds closed walking loops of a target length (default 883 m ± 50 m) on OSM footpaths within a radius (default 700 m) of a point. All loops go into one KML, closest to the target length first, and each loop is also written as its own GPX track.

## How to Run

- `make country` (one-time Vietnam extract; needs `osmium`)
- `make run LAT=20.9947 LON=105.8679` (also `RADIUS`, `TARGET`, `EPSILON`)

Outputs go to `data/<lat>_<lon>_<radius>m/`: `footpaths.osm`, `loops.kml`, `gpx/loop_NNN_<length>m.gpx`.

## Workflow

1. Clip the country extract to the circle's bounding box and keep `highway=footway|path|pedestrian|steps` ways.
2. Build a graph from nodes inside the circle, collapse it to undirected (shortest parallel edge wins), and prune it to its 2-core.
3. Depth-first search for simple cycles within the length window. Each cycle is found once, from its lowest node ID, and a branch is cut when its length plus the straight-line distance back to the start would overshoot.
4. Stop after `MAX_LOOPS` (500) loops, sort them by distance from the target length, and export.
