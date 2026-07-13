"""Shared helpers for local Ollama JSON generation."""

from __future__ import annotations

import json
from typing import Any

import requests
from config import OLLAMA_MODEL, OLLAMA_URL


def ensure_model(model: str = OLLAMA_MODEL) -> None:
    response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=10)
    response.raise_for_status()
    installed = {item["name"].split(":")[0] for item in response.json().get("models", [])}
    base_name = model.split(":")[0]
    if base_name not in installed:
        print(f"Model {model} not found locally. Pulling with ollama...")
        pull = requests.post(
            f"{OLLAMA_URL}/api/pull",
            json={"name": model, "stream": False},
            timeout=600,
        )
        pull.raise_for_status()


def generate_json(
    prompt: str,
    model: str = OLLAMA_MODEL,
    temperature: float = 0.1,
) -> dict[str, Any]:
    response = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": temperature},
        },
        timeout=120,
    )
    response.raise_for_status()

    raw = response.json().get("response", "{}")
    try:
        result: dict[str, Any] = json.loads(raw)
        return result
    except json.JSONDecodeError:
        return {"error": f"Unparseable model response: {raw[:200]}"}
