# Use vibe-mapping often

The useful part is already there: OSM features rolled into a few cells, each with a felt character. What keeps it on the shelf is everything wrapped around that.

## What makes it hard to open

A look at one neighborhood is a country extract, osmium, a Makefile edit for the pin, seven files, then a KML upload into Google My Maps. The sentence you came for is the last stage, and it is one local LLM call per cell. A 5 km circle is on the order of a hundred cells, so the interesting step is also the slow one.

Those sentences are paraphrases. The prompt forbids inventing anything, so the model restates scores already computed. The scores are min-maxed inside that one run, and several of them are sums, so they run past 1 (`busy` and `walkable` can reach 2, `green_quiet` can go negative). The prompt still talks about them as a 0–1 feel. A cell that is the busiest in this extract reads the same as a cell that is actually overwhelming, and the wording drifts from the numbers.

The place is baked into the Makefile (Da Lat, with other pins commented out). Repeat use means editing source.

## Changes

**One command, one map.** `make look LAT=… LON=…` or `make look GPX=…` ends in a local HTML map. Color cells by two or three signals (traffic, green, how peopled it is) and put one short line in the popup. `gpx-map` and `photo-map` already work this way. KML stays as an export.

**A template is the default voice.** Pick the top signals and write the line in code: "quiet green edge, little traffic, a few cafés." Same inputs, same sentence, no Ollama on the path you run often. Keep the model as an optional pass over the whole walk — one call, one paragraph — for when you want prose. Drop the per-cell chat.

**Let a number mean the same thing next week.** Color and label from shares and densities (green share, major-road share, food count), not from who won the min-max inside this extract. Relative coloring stays as a switch when you want contrast inside one run.

**Ask Overpass for the circle.** Overpass already runs in `geo-stack`. A bbox query for the tags you keep is the hop for "what is this neighborhood." Keep the country PBF and osmium for a long GPX you want clipped completely. Cache by bbox and resolution so the second look is free.

**Stop shipping the second map by default.** The category KML is a different product (every feature, thirteen colors). Take it off `make run`. Thirteen categories can collapse toward the signals the sentence actually uses: food, green and water, traffic, residential, people. Keep the cell builder. It is most of the code because the geometry is the product.

## Leave alone

The cell engine, the GPX filter that keeps only cells the route passes through, and the tests around scoring. That is the ground-truth path: run somewhere, then compare the map with what you saw. The cut is the ceremony in front of it.

## First slice

Local map plus template lines from the scores already written, with the pin on the command line. Overpass, and dropping the per-cell model, come after that slice feels like something you would open.
