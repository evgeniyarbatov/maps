# How the loop search works

The goal: find simple cycles (no repeated node) in the footpath network inside a circle whose length is within `TARGET ± EPSILON`, prefer the ones inside parks, and keep those that aren't near-duplicates of each other.

## Pipeline

```
country .osm.pbf
  → osmium extract (bbox) → osmium tags-filter (footpaths)   footpaths.osm
  → graph of nodes inside the circle
  → undirected simple graph → 2-core
  → chain contraction (junction graph)
  → bounded beam cycle search
  → rank park loops first, then |length − target|; drop overlapping loops
  → loops.kml + gpx/loop_NNN_<len>m.gpx
```

## 1. Extract footpaths

- The circle's bounding box is computed from the radius (latitude span is radius / Earth radius; longitude span is widened by `1 / cos(lat)`).
- `osmium extract -b` clips the country file to that box; `osmium tags-filter` keeps ways tagged `highway=footway|path|pedestrian|steps` plus the nodes they reference.
- Roads, sidewalks mapped as `footway=sidewalk` on roads, tracks, cycleways etc. are not included — only the four highway values above.

## 2. Build the graph

- Every OSM node within the radius (haversine distance from the centre) becomes a graph node.
- Every pair of consecutive nodes in a footpath way becomes an edge weighted by the haversine distance between them. A segment with an endpoint outside the circle is skipped, which is why paths crossing the circle edge get cut.
- The graph is collapsed to undirected and simple: self-loops are dropped, and when two ways connect the same pair of nodes the shorter edge is kept.

## 3. Prune to the 2-core

The 2-core is what's left after repeatedly deleting nodes of degree < 2. A dead-end spur can never be part of a cycle, so this removes nothing a loop could use while shrinking the graph a lot (OSM footpaths are full of stubs). `--no-k-core` skips it; the search is still correct, just slower.

## 4. Contract chains

Most OSM nodes are shape points with exactly two neighbours. A cycle that enters such a run must traverse all of it, so runs are collapsed:

- A **junction** is a node with degree ≠ 2. A connected component with no junctions (a pure ring) gets its lowest node promoted to a junction so it has an anchor.
- A **chain** is the walk from one junction through degree-2 nodes to the next junction. It stores both end junctions, total length, and the full node list so it can be expanded back later.
- Two junctions can be joined by several parallel chains, and a chain can start and end at the same junction (a ring hanging off a junction). Chains are therefore identified by their own ID, not by their endpoints.
- Junctions are renumbered `0..n−1`. Paths track which junctions and chains they use as bitmasks over those IDs.

Every simple cycle in the original graph is now exactly a cyclic sequence of distinct chains that visits each junction at most once. The search runs on this much smaller junction multigraph.

## 5. Enumerate cycles (bounded beam)

Listing every simple path up to half a lap is exponential on a sidewalk grid, where junctions sit a few tens of metres apart. The search therefore keeps at most `BEAM_WIDTH` partial paths to each junction in each `BAND_M` length band, and does not extend anything beyond that.

Each cycle is grown only from its **lowest-numbered junction `s`**. The walk may enter only junctions numbered above `s`, and it may not repeat a junction or a chain. A chain that returns to `s` with length inside `TARGET ± EPSILON` is recorded. The other direction uses the same chains, so the cycle is stored once, keyed by that set.

The width is enough for the 4×4 grid test to match an exhaustive listing. On a dense graph the result is a sample: every returned loop is a real simple cycle in the window, and the search stops.

## 6. Rank and de-duplicate

On a dense network many cycles differ only by a short detour, which isn't useful when picking a lap. So:

1. A loop is a park loop when at least half its nodes lie in a `leisure=park` or `leisure=garden` polygon, or a `landuse=recreation_ground` polygon. Multipolygon holes do not count. The same circle clip supplies those polygons.
2. Park loops come first, then `|length − TARGET|`.
3. They're taken greedily in that order. A candidate is dropped if more than `MAX_OVERLAP` (default 0.5) of **its** length lies on chains already used by any single kept loop. Overlap is measured at chain granularity via an index from chain to kept loops.
4. Stops at `MAX_LOOPS` (default 500) kept loops.

## 7. Export

- Each kept loop's chain sequence is expanded back to OSM nodes (chains reversed when walked from their far end), starting and ending at `s`.
- `loops.kml` has one coloured line per loop, named with its length and the delta from target. Colours step hue by the golden angle (≈137.5°) and alternate saturation/brightness so neighbouring loops look distinct.
- One GPX track per loop goes to `gpx/`, named `loop_NNN_<length>m.gpx` in rank order; previous GPX files are removed first.

## Limitations

- Lengths are straight-line distances between consecutive OSM nodes; no elevation, so real distance on steep paths is slightly longer.
- Only simple cycles: a lap that repeats a stretch of path (e.g. an out-and-back tail) is never found.
- On a dense graph the beam drops partial paths, so some cycles in the window are never returned.
- A park whose boundary misses the clip is ignored. When the whole circle sits inside one park, every loop is in it and the rank does not change.
- Results depend on how footpaths are tagged in OSM; sidewalks tagged on roads are invisible.
