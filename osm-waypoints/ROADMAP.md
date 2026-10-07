# Roadmap

## Why keep going

This is the closest thing in the portfolio to a finished product: extract → LLM-filter → LLM-describe → render → export, with real test coverage, working end to end against a real trail (nui-dinh). The interesting part isn't the pipeline mechanics — it's that a local model is doing real curatorial work (filtering OSM misclassifications, writing short labels) instead of just being a novelty layer on top of a GIS script.

## What it opens up

The pipeline currently defaults to one trail. Running it against a genuinely different region (different terrain, different OSM tagging density) is the real test of whether the POI rules and buffer defaults generalize — or whether "works great on nui-dinh" was partly luck. Once that's answered, this becomes a general "give me interesting waypoints for any GPX set" tool instead of a bespoke pipeline for one trail.

## Capability this builds

Using a local LLM as a *filter and editor* over structured data rather than a generator from scratch — trusting it to say "this OSM tag is wrong" or "this needs a shorter label," which is a narrower and more reliable use of an LLM than open-ended generation.

