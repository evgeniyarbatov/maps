#!/usr/bin/env python3
"""Generate brief waypoint descriptions with Ollama from OSM attributes."""

from __future__ import annotations

import json
import sys
import time

from config import OLLAMA_MODEL, POIS_VALIDATED
from ollama_client import ensure_model, generate_json
from osm_context import build_description_context
from text_utils import normalize_description

PROMPT_TEMPLATE = """Write a brief waypoint description for someone walking on foot.

Rules:
- 1 sentence maximum
- plain English, ASCII only
- use only facts present in the OSM context below
- do not invent history, dates, or features
- if context is sparse, describe the place type and any named detail available

OSM context:
{context}

Reply with JSON only:
{{"description": "one sentence"}}
"""


def describe_poi(poi: dict, model: str) -> str:
    context = build_description_context(poi)
    prompt = PROMPT_TEMPLATE.format(context=json.dumps(context, ensure_ascii=False, indent=2))
    result = generate_json(prompt, model=model, temperature=0.2)
    return normalize_description(str(result.get("description", "")))


def main() -> int:
    if not POIS_VALIDATED.is_file():
        print(
            f"Validated POI file not found: {POIS_VALIDATED}\nRun `make validate-pois` first.",
            file=sys.stderr,
        )
        return 1

    payload = json.loads(POIS_VALIDATED.read_text())
    waypoints = payload.get("waypoints", [])
    kept = [poi for poi in waypoints if poi.get("valid")]

    if not kept:
        print("No kept POIs to describe.")
        return 0

    try:
        ensure_model(OLLAMA_MODEL)
    except Exception as exc:
        print(f"Cannot reach Ollama: {exc}", file=sys.stderr)
        return 1

    described = 0
    for index, poi in enumerate(waypoints, start=1):
        if not poi.get("valid"):
            continue

        print(f"[{described + 1}/{len(kept)}] {poi['name']} ({poi['category']})")
        try:
            description = describe_poi(poi, OLLAMA_MODEL)
        except Exception as exc:
            print(f"  skipped: {exc}", file=sys.stderr)
            continue

        poi["description"] = description
        described += 1
        if description:
            print(f"  desc: {description}")
        else:
            print("  desc: (empty)")
        time.sleep(0.1)

    payload["description_model"] = OLLAMA_MODEL
    payload["described"] = described
    POIS_VALIDATED.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")

    print(f"Described {described} kept POIs in {POIS_VALIDATED}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())