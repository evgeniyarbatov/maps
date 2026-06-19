#!/usr/bin/env python3
"""Filter POIs with a local Ollama model to remove OSM misclassifications."""

from __future__ import annotations

import json
import sys
import time

from config import OLLAMA_MODEL, POIS_RAW, POIS_VALIDATED
from ollama_client import ensure_model, generate_json

PROMPT_TEMPLATE = """You help someone plan a walk on foot and curate OpenStreetMap points of interest.

Decide whether this POI is interesting to notice, visit, or walk past during a casual on-foot outing.
This is not limited to mountain hiking — city walks, village strolls, forest paths, and scenic routes all count.

Keep POIs that add interest to a walk, such as:
- viewpoints, peaks, parks, lakes, beaches, caves
- temples, churches, pagodas, shrines, monuments, ruins, historic sites
- museums, artwork, landmarks, picnic spots, notable buildings
- anything with a clear name or story that a walker might want to see

Only reject POIs that are clearly not walk-relevant, such as:
- generic shops, restaurants, hotels, offices, parking, fuel stations
- unnamed utility buildings with no sightseeing value
- obvious OSM tagging mistakes (e.g. a convenience store tagged as a viewpoint)

When unsure, prefer keeping the POI.

POI name: {name}
Category: {category}
OSM tags: {tags}

Reply with JSON only:
{{"valid": true, "reason": "short explanation"}}
or
{{"valid": false, "reason": "short explanation"}}
"""


def classify_poi(poi: dict, model: str) -> dict:
    prompt = PROMPT_TEMPLATE.format(
        name=poi["name"],
        category=poi["category"],
        tags=json.dumps(poi["tags"], ensure_ascii=False),
    )
    verdict = generate_json(prompt, model=model)

    valid = bool(verdict.get("valid"))
    reason = str(verdict.get("reason", verdict.get("error", ""))).strip()

    return {**poi, "valid": valid, "validation_reason": reason}


def main() -> int:
    if not POIS_RAW.is_file():
        print(f"POI file not found: {POIS_RAW}\nRun `make extract-pois` first.", file=sys.stderr)
        return 1

    payload = json.loads(POIS_RAW.read_text())
    pois = payload.get("waypoints", [])
    if not pois:
        print("No POIs to validate.")
        POIS_VALIDATED.write_text(json.dumps({"count": 0, "waypoints": []}, indent=2) + "\n")
        return 0

    try:
        ensure_model(OLLAMA_MODEL)
    except Exception as exc:
        print(f"Cannot reach Ollama: {exc}", file=sys.stderr)
        return 1

    validated: list[dict] = []
    kept = 0

    for index, poi in enumerate(pois, start=1):
        print(f"[{index}/{len(pois)}] {poi['name']} ({poi['category']})")
        try:
            result = classify_poi(poi, OLLAMA_MODEL)
        except Exception as exc:
            print(f"  skipped: {exc}", file=sys.stderr)
            continue

        status = "keep" if result["valid"] else "drop"
        print(f"  {status}: {result['validation_reason']}")
        validated.append(result)
        if result["valid"]:
            kept += 1
        time.sleep(0.1)

    output = {
        "source": str(POIS_RAW),
        "model": OLLAMA_MODEL,
        "count": len(validated),
        "kept": kept,
        "waypoints": validated,
    }
    POIS_VALIDATED.parent.mkdir(parents=True, exist_ok=True)
    POIS_VALIDATED.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")

    print(f"Validated {len(validated)} POIs, kept {kept}. Wrote {POIS_VALIDATED}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())