# Roadmap

Extracts OSM points of interest along GPX walking tracks, filters them with a local Ollama model, and exports Garmin-ready GPX waypoints with per-type icons and short labels.

## Where this stands

Full pipeline works end to end (extract → filter → describe → render → export), has real unit test coverage, and defaults to a specific local trail (`nui-dinh`).

## Next

- Add CI to run the existing test suite on every push (see TODO.md).
- Try the pipeline against a GPX set from a different region to check the POI rules and buffer defaults generalize beyond the current default trail.
