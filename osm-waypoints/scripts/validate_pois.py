#!/usr/bin/env python3
"""Filter POIs with a local Ollama model to remove OSM misclassifications."""

from __future__ import annotations

import json
import sys
import time

import requests

from config import OLLAMA_MODEL, OLLAMA_URL, POIS_RAW, POIS_VALIDATED

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


def ensure_model(model: str) -> None:
    response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=10)
    response.raise_for_status()
    installed = {item["name"].split(":")[0] for item in response.json().get("models", [])}
    base_name = model.split(":")[0]
    if base_name not in installed:
        print(f"Model {model} not found locally. Pulling with ollama...")
        subprocess_pull = requests.post(
            f"{OLLAMA_URL}/api/pull",
            json={"name": model, "stream": False},
            timeout=600,
        )
        subprocess_pull.raise_for_status()


def classify_poi(poi: dict, model: str) -> dict:
    prompt = PROMPT_TEMPLATE.format(
        name=poi["name"],
        category=poi["category"],
        tags=json.dumps(poi["tags"], ensure_ascii=False),
    )

    response = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.1},
        },
        timeout=120,
    )
    response.raise_for_status()

    raw = response.json().get("response", "{}")
    try:
        verdict = json.loads(raw)
    except json.JSONDecodeError:
        verdict = {"valid": False, "reason": f"Unparseable model response: {raw[:200]}"}

    valid = bool(verdict.get("valid"))
    reason = str(verdict.get("reason", "")).strip()

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
    except requests.RequestException as exc:
        print(f"Cannot reach Ollama at {OLLAMA_URL}: {exc}", file=sys.stderr)
        return 1

    validated: list[dict] = []
    kept = 0

    for index, poi in enumerate(pois, start=1):
        print(f"[{index}/{len(pois)}] {poi['name']} ({poi['category']})")
        try:
            result = classify_poi(poi, OLLAMA_MODEL)
        except requests.RequestException as exc:
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