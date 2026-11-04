# Footway Loops

Finds a self-transcendence running loop in your neighborhood: a short closed loop of footpaths you can run round and round for an ultra distance without leaving home. The default 883 m is the lap of the [Self-Transcendence 3100 Mile Race](https://en.wikipedia.org/wiki/Self-Transcendence_3100_Mile_Race) in New York. Background: [Find a Self-Transcendence Running Loop in Your Neighborhood](https://arbatov.substack.com/p/find-a-self-transcendence-running).

## How to Run

- `make run LOCATION=20.99,105.8679` (also `RADIUS`, `TARGET`, `EPSILON`); fetches the Vietnam extract first if missing or stale. Needs `osmium`.

Outputs go to `~/Documents/data/footway-loops/<lat>_<lon>_<radius>m/` (override with `DATA_DIR=` or `DATA_ROOT=`): `footpaths.osm`, `parks.osm`, `roads.osm`, `loops.kml`, `gpx/loop_NNN_<length>m.gpx`. Import `loops.kml` into Google My Maps to compare loops, then load the chosen GPX onto your watch.

## Workflow

1. Clip the country extract to the circle's bounding box and keep `highway=footway|path|pedestrian|steps` ways. The same clip supplies park polygons and vehicle roads (motorway down to service, including links).
2. Build a graph from nodes inside the circle. Leave out a segment that is a mapped crossing or that cuts a vehicle road at the same level. Collapse the graph to undirected (shortest parallel edge wins) and prune it to its 2-core.
3. Contract runs of degree-2 nodes into chains between junctions. Search simple cycles within `TARGET ± EPSILON` with a bounded beam (24 partial paths per junction in each 40 m band), so a dense sidewalk grid finishes.
4. Drop any remaining loop that steps from one side of a vehicle road to the other. Rank the rest by fewer turns, then loops inside parks, then distance from the target length. Drop loops that share more than half their length with a better one, and keep the top 10.

## Limits

Loops are searched on `highway=footway|path|pedestrian|steps` inside the radius, wherever the point sits. A loop that crosses a vehicle road is left out: a mapped crossing, a segment that cuts a carriageway, or a path that steps from one side of a road to the other. Service roads count. A sidewalk that stays beside a road stays in, and so does a bridge or tunnel on a different level.

The file lists at most 10 of the loops that remain, smoothest first: a turn is a heading change of at least 30°. Among loops with the same number of turns, one with at least half its nodes in a park, garden, or recreation ground comes before one that is not, then the length closer to the target. A point with no mapped park still returns walkable loops. A loop that shares more than half its length with a better one is dropped, so a park-heavy circle can come back with only park loops.

`make run` clips the Vietnam extract. The script itself takes any extract with `--pbf`; a point outside the file returns nothing.

- Only simple cycles. A lap that goes out and back on the same path is never found.
- On a dense sidewalk grid the beam keeps 24 partial paths per junction in each 40 m band, so some loops in the length window are missed. Every loop that is written is a real cycle in that window.
- A sidewalk that exists only as a tag on a road is missing, and so are tracks and cycleways.
- Nodes outside the radius are dropped, so a path that crosses the circle is cut.
- Length is the straight-line distance between OSM nodes, with no elevation.

Details: [docs/algorithm.md](docs/algorithm.md).
