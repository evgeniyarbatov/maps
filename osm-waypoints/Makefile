# Uses uv (https://docs.astral.sh/uv) for dependency management — uv sync creates/updates .venv; run commands via uv run, no manual activation.
# osm-waypoints pipeline

DATA_ROOT ?= $(HOME)/Documents/data
REPO_NAME := $(notdir $(CURDIR))
DATA_DIR  ?= $(DATA_ROOT)/$(REPO_NAME)

GPX_DIR ?= /Users/arbatov/Documents/gpx/nui-dinh
BUFFER_KM ?= 0.25
OLLAMA_MODEL ?= mistral-nemo
OLLAMA_URL ?= http://localhost:11434
MAP_DPI ?= 300

OSM_URL = https://download.geofabrik.de/asia/vietnam-latest.osm.pbf

DOTFILES_MK := $(HOME)/gitRepo/dotfiles/make/osm-country.mk
OSM_DIR := $(DATA_DIR)/osm

.DEFAULT_GOAL := help

.PHONY: country osm-country-fetch

ifneq ($(wildcard $(DOTFILES_MK)),)
include $(DOTFILES_MK)
else
country osm-country-fetch:
	@echo "error: '$@' needs evgeniyarbatov/dotfiles (private helper); not found at $(DOTFILES_MK)." >&2
	@echo "Fetch manually: download $(OSM_URL) into $(OSM_DIR)/$(COUNTRY_OSM_FILE), then retry." >&2
	@exit 1
endif

COUNTRY_OSM_FILE = $(notdir $(OSM_URL))

SCRIPTS_DIR = scripts

export GPX_DIR BUFFER_KM OLLAMA_MODEL OLLAMA_URL MAP_DPI DATA_DIR OSM_DIR

.PHONY: setup brew-deps lock test country extract-osm extract-pois validate-pois describe-pois render-map export-gpx all help

setup:
	@uv sync --all-packages

brew-deps:
	@command -v brew >/dev/null 2>&1 || { \
		echo "Homebrew is required. Install from https://brew.sh"; \
		exit 1; \
	}
	@brew bundle check --file=Brewfile >/dev/null 2>&1 || brew bundle --file=Brewfile

lock:
	@uv lock

test: setup
	@PYTHONPATH=$(SCRIPTS_DIR) uv run python -m unittest discover -s tests -p 'test_*.py' -v

extract-osm: setup brew-deps country
	@cd $(SCRIPTS_DIR) && PYTHONUNBUFFERED=1 uv run python extract_osm.py

extract-pois: setup extract-osm
	@cd $(SCRIPTS_DIR) && uv run python extract_pois.py
validate-pois: setup extract-pois
	@cd $(SCRIPTS_DIR) && uv run python validate_pois.py
describe-pois: setup validate-pois
	@cd $(SCRIPTS_DIR) && uv run python describe_pois.py
render-map: setup describe-pois
	@cd $(SCRIPTS_DIR) && uv run python render_map.py
export-gpx: setup describe-pois
	@cd $(SCRIPTS_DIR) && uv run python export_gpx.py
all: export-gpx render-map

help:
	@echo "run           - full waypoints extraction pipeline"
	@echo "setup         - uv sync"
	@echo "brew-deps     - install/check Homebrew deps (osmium-tool, ollama)"
	@echo "lock          - refresh uv.lock"
	@echo "test          - run unit tests"
	@echo "country       - download/link country OSM extract"
	@echo "extract-osm   - build buffered polygon and cut country PBF"
	@echo "extract-pois  - parse OSM extract into $(DATA_DIR)/pois.json"
	@echo "validate-pois - Ollama filter pass"
	@echo "describe-pois - Ollama description pass"
	@echo "render-map    - render $(DATA_DIR)/waypoints.png"
	@echo "export-gpx    - export $(DATA_DIR)/waypoints.gpx"
	@echo "all           - export-gpx render-map"

# Entry point: full waypoints extraction pipeline.
run: all
