# Roadmap

## Why keep going

This is the closest thing in the portfolio to a finished product: extract → LLM-filter → LLM-describe → render → export, with real test coverage, working end to end against a real trail (nui-dinh). The interesting part isn't the pipeline mechanics — it's that a local model is doing real curatorial work (filtering OSM misclassifications, writing short labels) instead of just being a novelty layer on top of a GIS script.

## What it opens up

The pipeline currently defaults to one trail. Running it against a genuinely different region (different terrain, different OSM tagging density) is the real test of whether the POI rules and buffer defaults generalize — or whether "works great on nui-dinh" was partly luck. Once that's answered, this becomes a general "give me interesting waypoints for any GPX set" tool instead of a bespoke pipeline for one trail.

## Capability this builds

Using a local LLM as a *filter and editor* over structured data rather than a generator from scratch — trusting it to say "this OSM tag is wrong" or "this needs a shorter label," which is a narrower and more reliable use of an LLM than open-ended generation.

## Connects to

**[private]** and **[private]** — both extract "good to walk near" OSM features by tag; a natural POI source to cross-check against once this pipeline runs on more than one trail. **[private]** — a different way of enriching a route with context (street-level imagery instead of curated waypoints); worth comparing which enrichment actually gets used on a real run. **[private]** and **[private]** — both customize GPX output; this pipeline's Garmin-ready export is the same kind of "make it usable on the device" last step.
