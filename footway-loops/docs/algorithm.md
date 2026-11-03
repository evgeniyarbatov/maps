# How the loop search works

The goal: list every simple cycle (no repeated node) in the footpath network inside a circle whose length is within `TARGET ± EPSILON`, then keep the closest-to-target ones that aren't near-duplicates of each other.

## Pipeline

```
country .osm.pbf
  → osmium extract (bbox) → osmium tags-filter (footpaths)   footpaths.osm
  → graph of nodes inside the circle
  → undirected simple graph → 2-core
  → chain contraction (junction graph)
  → meet-in-the-middle cycle enumeration
  → rank by |length − target|, drop overlapping loops
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

## 5. Enumerate cycles (meet in the middle)

A naive DFS from each start node explores every path up to the full target length; the number of paths grows exponentially with length. Instead, each cycle is split into two halves, and only half-length paths are explored.

### Anchor

Each cycle is generated only from its **lowest-numbered junction `s`**. When searching from `s`, the search never steps onto a junction below `s`. This gives each cycle one anchor without needing a "seen" set.

### Half-paths

From `s`, a DFS lists every simple path that:

- only visits junctions numbered above `s`,
- has length ≤ `(TARGET + EPSILON) / 2`.

The trivial zero-length path at `s` is included. Paths are grouped by end junction and sorted by length.

### Splitting a cycle at its midpoint

Walk a cycle from `s` in one direction. The point at distance `total / 2` lies inside exactly one chain (the one with start ≤ `total/2` < end) — the **midpoint chain**. Removing it leaves two half-paths from `s`, each no longer than `total / 2`:

```
            out (≤ total/2)
     s ───────────────────────► u
     │                          │
     │                          │  midpoint chain (u → v)
     │                          │
     └────────────────────────► v
            back (≤ total/2)
```

So for every half-path `out` ending at `u`, and every chain from `u` to some `v`, the search looks up half-paths `back` ending at `v` and accepts the pair when:

- **Length window:** `out + mid + back` is within `TARGET ± EPSILON`.
- **Midpoint condition:** `out − mid ≤ back < out + mid`, which is the algebraic form of "the cycle's midpoint falls inside this chain". This makes each (cycle, direction) produce exactly one split.
- **Disjoint:** `out` and `back` share no junction except `s`, neither uses the midpoint chain, and `v` is not already on `out` (unless `v = s`, which closes the cycle directly with an empty `back`).

Because `back` lists are sorted by length, a binary search jumps to the first `back` that satisfies both lower bounds, and the scan stops at the first one that breaks an upper bound.

### One direction only

Every cycle can be walked two ways from `s`, and each direction yields its own split. The pair is kept only when the first chain of `out` has an ID ≤ the first chain of `back` (an empty half counts the midpoint chain as its first). The two directions swap which chain leaves `s` first, so exactly one survives.

Net effect: every simple cycle in the length window is produced exactly once, and the search only ever explores paths of half the target length — roughly a square-root reduction in the number of explored paths compared with a full-length DFS. The test suite checks the count against `networkx.simple_cycles` on a grid.

## 6. Rank and de-duplicate

On a dense network many cycles differ only by a short detour, which isn't useful when picking a lap. So:

1. All candidates are sorted by `|length − TARGET|`.
2. They're taken greedily in that order. A candidate is dropped if more than `MAX_OVERLAP` (default 0.5) of **its** length lies on chains already used by any single kept loop. Overlap is measured at chain granularity via an index from chain to kept loops.
3. Stops at `MAX_LOOPS` (default 500) kept loops.

The chosen loops are therefore the closest to target globally, not the first ones found.

## 7. Export

- Each kept loop's chain sequence is expanded back to OSM nodes (chains reversed when walked from their far end), starting and ending at `s`.
- `loops.kml` has one coloured line per loop, named with its length and the delta from target. Colours step hue by the golden angle (≈137.5°) and alternate saturation/brightness so neighbouring loops look distinct.
- One GPX track per loop goes to `gpx/`, named `loop_NNN_<length>m.gpx` in rank order; previous GPX files are removed first.

## Limitations

- Lengths are straight-line distances between consecutive OSM nodes; no elevation, so real distance on steep paths is slightly longer.
- Only simple cycles: a lap that repeats a stretch of path (e.g. an out-and-back tail) is never found.
- All candidates are held in memory before ranking; very large radii or epsilons can blow up.
- Results depend on how footpaths are tagged in OSM; sidewalks tagged on roads are invisible.
