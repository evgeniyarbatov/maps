# Roadmap

Estimates the real-world width of an OSM way by comparing it against many GPS polylines that cross it (currently Strava running activities), using perpendicular offset distributions with outlier filtering.

## Where this stands

Ships with a working example (Times City boundary + polylines) and produces both an aggregate width and 10 m-segment widths with plots.

## Next

- Feed estimated `width_m` back into `[private]`, which needs exactly this to compute its `λ / w` and `R / w` ratios for OSM ways that currently have no width data.
- Extend beyond a single hand-picked way per run to cover a whole area's ways in one pass.
