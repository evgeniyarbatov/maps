# How the loop search works

The goal: find simple cycles (no repeated node) in the footpath network inside a circle whose length is within `TARGET ± EPSILON`, leave out any loop that crosses a vehicle road or folds two sharp corners together, prefer the ones inside parks, and keep those that aren't near-duplicates of each other.

## Pipeline

```
country .osm.pbf
  → osmium extract (bbox)
       → tags-filter footpaths     footpaths.osm
       → tags-filter parks         parks.osm
       → tags-filter roads         roads.osm
  → graph of nodes inside the circle, without road crossings
  → undirected simple graph → 2-core
  → chain contraction (junction graph)
  → bounded beam cycle search
  → drop loops that cross a vehicle road, or whose sharp corners are under 15 m apart
  → fewest turns, then park loops, then |length − target|; drop overlapping loops
  → loops.kml + gpx/loop_NNN_<len>m.gpx
```

## 1. Extract

- The circle's bounding box is computed from the radius (latitude span is radius / Earth radius; longitude span is widened by `1 / cos(lat)`).
- One `osmium extract -b` clips the country file. Three `osmium tags-filter` passes read that clip, then the clip is deleted.
- Footpaths are ways tagged `highway=footway|path|pedestrian|steps`, plus the nodes they reference. A sidewalk drawn as its own footway is included. A sidewalk that is only a tag on a road is not, and neither are tracks or cycleways.
- Parks are ways and relations tagged `leisure=park`, `leisure=garden`, or `landuse=recreation_ground`. The filter keeps relation members, so a multipolygon's outer ways are in `parks.osm` even when those ways have no park tag.
- Vehicle roads are ways tagged `highway` as motorway, trunk, primary, secondary, tertiary, unclassified, residential, living_street, service, or road, plus the link forms of motorway, trunk, primary, secondary, and tertiary. They are written to `roads.osm`. Service roads are included.

## 2. Build the graph

- Every OSM node within the radius (haversine distance from the centre) becomes a graph node.
- Every pair of consecutive nodes in a footpath way becomes an edge weighted by the haversine distance between them. A segment with an endpoint outside the circle is skipped, which is why paths crossing the circle edge get cut.
- A segment is also skipped when its way is a crossing (`footway=crossing` or `traffic_island`, or any `crossing` tag other than `no`), or when it meets a vehicle road of the same grade. Same grade means the open segments intersect, or a footpath end lies in the interior of a road segment. A shared endpoint does not count. Grade is the `layer` tag when it is a number; otherwise a bridge is 1 and a tunnel is -1.
- The graph is collapsed to undirected and simple: self-loops are dropped, and when two ways connect the same pair of nodes the shorter edge is kept. Its grade is kept with it.

## 3. Prune to the 2-core

The 2-core is what's left after repeatedly deleting nodes of degree < 2. A dead-end spur can never be part of a cycle, so this removes nothing a loop could use while shrinking the graph a lot (OSM footpaths are full of stubs). `--no-k-core` skips it. The spurs still cannot close a loop, but they take beam slots, so the sample of cycles can change.

## 4. Contract chains

Most OSM nodes are shape points with exactly two neighbours. A cycle that enters such a run must traverse all of it, so runs are collapsed:

- A **junction** is a node with degree ≠ 2. A connected component with no junctions (a pure ring) gets its lowest node promoted to a junction so it has an anchor.
- A **chain** is the walk from one junction through degree-2 nodes to the next junction. It stores both end junctions, total length, and the full node list so it can be expanded back later.
- Two junctions can be joined by several parallel chains, and a chain can start and end at the same junction (a ring hanging off a junction). Chains are therefore identified by their own ID, not by their endpoints.
- Junctions are renumbered `0..n−1` in OSM-id order. Paths track which junctions and chains they use as bitmasks over those IDs.

Every simple cycle in the original graph is now exactly a cyclic sequence of distinct chains that visits each junction at most once. The search runs on this junction multigraph.

## 5. Enumerate cycles (bounded beam)

`BEAM_WIDTH` is 24. `BAND_M` is 40 m.

Each cycle is grown only from its lowest-numbered junction `s`. The walk may step to `s` only to close, and it never steps to a junction numbered below `s`, so each cycle has one start. It also may not repeat a junction or a chain.

From `s`, a breadth-first walk extends one chain at a time:

- A partial walk longer than `TARGET + EPSILON` is not extended.
- A chain that returns to `s` with length inside `TARGET ± EPSILON` is a cycle. It is stored under the set of its chains, so the opposite direction does not add a second copy.
- Any other arrival is kept only while that junction has fewer than 24 partial walks in the same 40 m band (`length // 40`). Further arrivals in a full band are dropped and not extended.

The queue is first-in-first-out, so those 24 walks are the ones reached first. They are not the 24 shortest, and they are not picked to spread out across the map.

Work per start is capped by junctions × length bands × 24. On the 4×4 test grid the cap is wide enough that the result matches an exhaustive cycle count. On a sidewalk grid the cap fills, and some cycles in the window are never grown. Every cycle that is returned is a real simple cycle in the window.

## 6. Parks, rank, and de-duplicate

A candidate is dropped when the walk steps from one side of a vehicle road to the other at the same grade. At a loop node that also lies on a road, both neighbouring points must sit at least 1 m off that road's line and on opposite sides. A corner, where one leg runs along the road, stays. A crossing drawn through the road's own node does not intersect the road segment, which is why this second check exists.

A candidate is also dropped when two heading changes of at least 60° lie under 15 m apart along the path, including across the point where the loop closes. A bend under 60° can sit next to a corner.

Both drops happen before the top 10 are chosen, so another loop can take the place.

Polygons are read from `parks.osm`:

- A closed way with a park tag is one outer ring.
- A relation's outer and inner ways are stitched where they share an endpoint. A member with no role counts as outer. A fragment that does not close is dropped.
- A point is inside a park when it is inside an outer ring and outside that park's holes. The test is an even-odd ray cast.

A loop is a park loop when at least half its nodes lie inside some park. The repeated closing node is not counted twice.

Then:

1. Fewer turns come first. A turn is a heading change of at least `TURN_ANGLE_DEG` (30°) at a node, including the corner where the loop closes. A shallower bend, and a shape point on a straight side, does not count.
2. Among loops with the same number of turns, park loops come first. Within that, smaller `|length − TARGET|` comes first, then shorter length.
3. Candidates are taken greedily in that order. One is dropped when more than `MAX_OVERLAP` (0.5) of **its** length lies on chains already used by any single kept loop. Overlap is measured per chain.
4. Stop at `MAX_LOOPS` (10). The first loop in the file is the one that won this order.

A loop that shares half its length with a smoother one already kept is dropped, even when its length is closer to the target.

## 7. Export

- Each kept loop's chain sequence is expanded back to OSM nodes (a chain is reversed when the walk enters it from its far end), starting and ending at `s`.
- `loops.kml` has one coloured line per loop, named with its length and its turn count, in rank order. Colours step hue by the golden angle (≈137.5°) and alternate saturation/brightness so neighbouring loops look distinct.
- One GPX track per loop goes to `gpx/`, named `loop_NNN_<length>m.gpx` in rank order; previous GPX files are removed first.

## Limitations

- Lengths are straight-line distances between consecutive OSM nodes; no elevation, so real distance on steep paths is slightly longer.
- Only simple cycles: a lap that repeats a stretch of path (an out-and-back tail) is never found.
- On a dense graph the beam drops partial walks, so some cycles in the window are never returned.
- A park whose boundary misses the clip is ignored. When the whole circle sits inside one park, every loop is a park loop and the preference does not change the order.
- Results depend on how footpaths are tagged in OSM. A sidewalk that was never drawn as its own way is invisible.
- A sidewalk that stays beside a road is kept. A crossing that is neither tagged, nor drawn across a road segment, nor stepped through a road node from one side to the other is not removed.
