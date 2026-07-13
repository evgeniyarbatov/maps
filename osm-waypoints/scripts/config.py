"""Shared configuration for the osm-waypoints pipeline."""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

GPX_DIR = Path(os.environ.get("GPX_DIR", "/Users/arbatov/Documents/gpx/nui-dinh"))
BUFFER_KM = float(os.environ.get("BUFFER_KM", "0.25"))
OSM_DIR = REPO_ROOT / "osm"
DATA_DIR = REPO_ROOT / "data"

OSM_URL = os.environ.get("OSM_URL", "https://download.geofabrik.de/asia/vietnam-latest.osm.pbf")
COUNTRY_OSM_FILE = OSM_DIR / Path(OSM_URL).name

OSM_EXTRACT = OSM_DIR / "extract.osm"
OSM_POLYGON = OSM_DIR / "extract-polygon.geojson"
POIS_RAW = DATA_DIR / "pois.json"
POIS_VALIDATED = DATA_DIR / "pois_validated.json"
MAP_IMAGE = DATA_DIR / "waypoints.png"
WAYPOINTS_GPX = DATA_DIR / "waypoints.gpx"

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "mistral-nemo")

MAP_DPI = int(os.environ.get("MAP_DPI", "300"))
MAP_WIDTH_IN = float(os.environ.get("MAP_WIDTH_IN", "16"))
