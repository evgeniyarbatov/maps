# Uses uv (https://docs.astral.sh/uv) for dependency management — uv sync creates/updates .venv; run commands via uv run, no manual activation.
# osm-waypoints pipeline

GPX_DIR ?= /Users/arbatov/Documents/gpx/nui-dinh
BUFFER_KM ?= 0.25
OLLAMA_MODEL ?= mistral-nemo
OLLAMA_URL ?= http://localhost:11434
MAP_DPI ?= 300

OSM_URL = https://download.geofabrik.de/asia/vietnam-latest.osm.pbf

DOTFILES_MK := $(HOME)/gitRepo/dotfiles/make/osm-country.mk

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

OSM_DIR = osm
DATA_DIR = data
SCRIPTS_DIR = scripts

export GPX_DIR BUFFER_KM OLLAMA_MODEL OLLAMA_URL MAP_DPI

.PHONY: install lock test country extract-osm extract-pois validate-pois describe-pois render-map export-gpx all clean help

install:
	@command -v brew >/dev/null 2>&1 || { \
		echo "Homebrew is required. Install from https://brew.sh"; \
		exit 1; \
	}
	@brew bundle check --file=Brewfile >/dev/null 2>&1 || brew bundle --file=Brewfile
	@uv sync

lock:
	@uv lock

test: install
	@PYTHONPATH=$(SCRIPTS_DIR) uv run python -m unittest discover -s tests -p 'test_*.py' -v

extract-osm: install country
	@cd $(SCRIPTS_DIR) && PYTHONUNBUFFERED=1 uv run python extract_osm.py

extract-pois: install extract-osm
	@cd $(SCRIPTS_DIR) && uv run python extract_pois.py
validate-pois: install extract-pois
	@cd $(SCRIPTS_DIR) && uv run python validate_pois.py
describe-pois: install validate-pois
	@cd $(SCRIPTS_DIR) && uv run python describe_pois.py
render-map: install describe-pois
	@cd $(SCRIPTS_DIR) && uv run python render_map.py
export-gpx: install describe-pois
	@cd $(SCRIPTS_DIR) && uv run python export_gpx.py
all: export-gpx render-map

clean:
	@rm -f $(OSM_DIR)/extract.osm $(OSM_DIR)/extract-polygon.geojson
	@rm -f $(DATA_DIR)/pois.json $(DATA_DIR)/pois_validated.json
	@rm -f $(DATA_DIR)/waypoints.png $(DATA_DIR)/waypoints.gpx
	@rm -rf .venv

help:
	@echo "install       - brew deps + uv sync"
	@echo "lock          - refresh uv.lock"
	@echo "test          - run unit tests"
	@echo "country       - download/link country OSM extract"
	@echo "extract-osm   - build buffered polygon and cut country PBF"
	@echo "extract-pois  - parse OSM extract into data/pois.json"
	@echo "validate-pois - Ollama filter pass"
	@echo "describe-pois - Ollama description pass"
	@echo "render-map    - render data/waypoints.png"
	@echo "export-gpx    - export data/waypoints.gpx"
	@echo "all           - export-gpx render-map"
	@echo "clean         - remove generated osm/data outputs and .venv"
