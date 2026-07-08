# osm-waypoints pipeline

VENV_PATH := .venv
PYTHON := $(VENV_PATH)/bin/python
PIP := $(VENV_PATH)/bin/pip
REQUIREMENTS := requirements.txt

GPX_DIR ?= /Users/arbatov/Documents/gpx/nui-dinh
BUFFER_KM ?= 0.25
OLLAMA_MODEL ?= mistral-nemo
OLLAMA_URL ?= http://localhost:11434
MAP_DPI ?= 300

OSM_URL = https://download.geofabrik.de/asia/vietnam-latest.osm.pbf
include $(HOME)/gitRepo/dotfiles/make/osm-country.mk
COUNTRY_OSM_FILE = $(notdir $(OSM_URL))

OSM_DIR = osm
DATA_DIR = data
SCRIPTS_DIR = scripts

export GPX_DIR BUFFER_KM OLLAMA_MODEL OLLAMA_URL MAP_DPI

.PHONY: venv install country extract-osm extract-pois validate-pois describe-pois render-map export-gpx all clean

venv:
	@uv venv $(VENV_PATH)

install: venv
	@command -v brew >/dev/null 2>&1 || { \
		echo "Homebrew is required. Install from https://brew.sh"; \
		exit 1; \
	}
	@brew bundle check --file=Brewfile >/dev/null 2>&1 || brew bundle --file=Brewfile
	@uv pip install -q -r $(REQUIREMENTS)


extract-osm: install country
	@cd $(SCRIPTS_DIR) && PYTHONUNBUFFERED=1 $(CURDIR)/$(PYTHON) extract_osm.py

extract-pois: extract-osm
	@cd $(SCRIPTS_DIR) && $(CURDIR)/$(PYTHON) extract_pois.py

validate-pois: extract-pois
	@cd $(SCRIPTS_DIR) && $(CURDIR)/$(PYTHON) validate_pois.py

describe-pois: validate-pois
	@cd $(SCRIPTS_DIR) && $(CURDIR)/$(PYTHON) describe_pois.py

render-map: describe-pois
	@cd $(SCRIPTS_DIR) && $(CURDIR)/$(PYTHON) render_map.py

export-gpx: describe-pois
	@cd $(SCRIPTS_DIR) && $(CURDIR)/$(PYTHON) export_gpx.py

all: export-gpx render-map

clean:
	@rm -f $(OSM_DIR)/extract.osm $(OSM_DIR)/extract-polygon.geojson
	@rm -f $(DATA_DIR)/pois.json $(DATA_DIR)/pois_validated.json
	@rm -f $(DATA_DIR)/waypoints.png $(DATA_DIR)/waypoints.gpx