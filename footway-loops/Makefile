# Uses uv (https://docs.astral.sh/uv) for dependency management — uv sync creates/updates .venv; run commands via uv run, no manual activation.

PYTHON := uv run python

DATA_ROOT ?= $(HOME)/Documents/data
DATA_DIR ?= $(DATA_ROOT)/$(notdir $(CURDIR))
OSM_URL = https://download.geofabrik.de/asia/vietnam-latest.osm.pbf

DOTFILES_MK := $(HOME)/gitRepo/dotfiles/make/osm-country.mk
OSM_DIR := $(DATA_DIR)

.DEFAULT_GOAL := help

.PHONY: country osm-country-fetch

ifneq ($(wildcard $(DOTFILES_MK)),)
include $(DOTFILES_MK)
else
COUNTRY_OSM_FILE ?= $(notdir $(OSM_URL))

country osm-country-fetch:
	@echo "error: '$@' needs evgeniyarbatov/dotfiles (private helper); not found at $(DOTFILES_MK)." >&2
	@echo "Fetch manually: download $(OSM_URL) into $(OSM_DIR)/$(COUNTRY_OSM_FILE), then retry." >&2
	@exit 1
endif

LOCATION ?= 20.9947,105.8679
RADIUS ?= 700
TARGET ?= 883
EPSILON ?= 50

.PHONY: setup lock test run help

setup:
	@uv sync --all-packages

lock:
	@uv lock

test: setup
	@$(PYTHON) -m unittest discover -s tests

run: setup country
	@$(PYTHON) scripts/find_loops.py --pbf $(OSM_DIR)/$(COUNTRY_OSM_FILE) --location $(LOCATION) --radius $(RADIUS) --target $(TARGET) --epsilon $(EPSILON) --out-dir $(DATA_DIR)

help:
	@echo "country - fetch the country OSM extract (one-time)"
	@echo "setup   - uv sync (create/update .venv and install deps)"
	@echo "lock    - uv lock (refresh uv.lock)"
	@echo "test    - run unit tests"
	@echo "run     - loops of TARGET±EPSILON m within RADIUS m of LOCATION=lat,lon -> KML + GPX"
