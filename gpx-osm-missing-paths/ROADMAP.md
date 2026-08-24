# Roadmap

Turns personal running/walking GPX traces into JOSM-ready OpenStreetMap contributions: clusters repeated traces of the same physical path, names them from nearby landmarks, and exports focused `.osm` extracts.

## Shipped

Full GPX-to-JOSM pipeline, multi-trace clustering, shared OSM cache reuse, prepared and released as a public repo, `make run` entry point, ruff/mypy --strict pass.

## Next

- CI on the existing test suite (see TODO.md) — worth prioritizing since the repo is public.
- No documented success rate yet (how many exported extracts actually got merged into OSM) — would be useful feedback on whether the naming/clustering heuristics are good enough.
