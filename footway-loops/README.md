# Footway Loops

Finds a self-transcendence running loop in your neighborhood: a short closed loop of footpaths you can run round and round for an ultra distance without leaving home. The default 883 m is the lap of the [Self-Transcendence 3100 Mile Race](https://en.wikipedia.org/wiki/Self-Transcendence_3100_Mile_Race) in New York. Background: [Find a Self-Transcendence Running Loop in Your Neighborhood](https://arbatov.substack.com/p/find-a-self-transcendence-running).

## How to Run

- `make run LOCATION=20.99,105.8679` (also `RADIUS`, `TARGET`, `EPSILON`); fetches the Vietnam extract first if missing or stale. Needs `osmium`.

Outputs go to `~/Documents/data/footway-loops/<lat>_<lon>_<radius>m/` (override with `DATA_DIR=` or `DATA_ROOT=`): `footpaths.osm`, `loops.kml`, `gpx/loop_NNN_<length>m.gpx`. Import `loops.kml` into Google My Maps to compare loops, then load the chosen GPX onto your watch.

## Workflow

1. Clip the country extract to the circle's bounding box and keep `highway=footway|path|pedestrian|steps` ways. The same clip supplies `leisure=park|garden` and `landuse=recreation_ground` polygons.
2. Build a graph from nodes inside the circle, collapse it to undirected (shortest parallel edge wins), and prune it to its 2-core.
3. Contract runs of degree-2 nodes into chains between junctions. Search simple cycles within `TARGET ± EPSILON` with a bounded beam: a few partial paths per junction per length band, so a dense sidewalk grid finishes.
4. Rank loops inside parks ahead of other walkable loops, then by distance from the target length. Drop loops that share more than half their length with a better one, keep up to `MAX_LOOPS` (500), and export.

Details: [docs/algorithm.md](docs/algorithm.md).
