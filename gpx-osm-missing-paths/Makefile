# uv: https://docs.astral.sh/uv — deps via `make setup` / `make install`, run with `uv run`
#
# Country OSM: shared cache from dotfiles (launchd com.arbatov.fetch-osm → ~/.cache/osm).
# Do not re-download Geofabrik here; call fetch-osm via osm-country.mk only.
URL = https://download.geofabrik.de/asia/vietnam-latest.osm.pbf
include $(HOME)/gitRepo/dotfiles/make/osm-country.mk

# City scope: any osmconvert .poly under osm/ (or absolute path). Default: HCMC.
OSM_DIR = osm
BOUNDARY_POLYGON ?= osm/hcm.poly
CITY := $(basename $(notdir $(BOUNDARY_POLYGON)))
CITY_OSM_PBF := $(OSM_DIR)/$(CITY).osm.pbf
CITY_OSM := $(OSM_DIR)/$(CITY).osm

.PHONY: help setup install country city osm-check \
	gpx process cluster filter-missing name extract pipeline \
	clean test lint

# Raw GPX source: github.com/evgeniyarbatov/[private], per-city GeoParquet exports.
# Optional LAT/LON/RADIUS_KM narrows `make gpx` to tracks near one point.
LAT ?= 10.787919410913423
LON ?= 106.70594249757384
RADIUS_KM ?= 30

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(firstword $(MAKEFILE_LIST)) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "OSM defaults: country=$(COUNTRY_OSM_PATH)"
	@echo "              city poly=$(BOUNDARY_POLYGON) → $(CITY_OSM_PBF)"
	@echo "Other city:   make city BOUNDARY_POLYGON=osm/other.poly"
	@echo "Other country: make country URL=https://download.geofabrik.de/…/foo-latest.osm.pbf"

setup: ## Create venv with uv, install deps
	uv venv
	uv pip install -e ".[dev]"
	@echo "✅ Setup complete. Copy env.example → .env if needed."

install: ## Install/update deps only
	uv pip install -e ".[dev]"

# --- Shared country PBF (dotfiles fetch-osm; no parallel download flow) ---

country: osm-country-fetch ## Ensure country PBF in ~/.cache/osm (weekly launchd also refreshes)

city: ## Clip country PBF to BOUNDARY_POLYGON → osm/<city>.osm.pbf (+ .osm)
	@test -f "$(BOUNDARY_POLYGON)" || (echo "Missing poly: $(BOUNDARY_POLYGON)" >&2; exit 1)
	@test -f "$(COUNTRY_OSM_PATH)" || (echo "Missing country PBF: $(COUNTRY_OSM_PATH). Run: make country (or wait for launchd com.arbatov.fetch-osm)" >&2; exit 1)
	@mkdir -p "$(OSM_DIR)"
	osmconvert "$(COUNTRY_OSM_PATH)" \
		-B=$(BOUNDARY_POLYGON) \
		--complete-ways \
		--complete-multipolygons \
		-o=$(CITY_OSM_PBF)
	osmium cat --overwrite "$(CITY_OSM_PBF)" -o "$(CITY_OSM)"
	@echo "✅ City extract: $(CITY_OSM_PBF) (from $(BOUNDARY_POLYGON))"

osm-check: ## Verify country cache + city extract exist
	@test -f "$(COUNTRY_OSM_PATH)" || (echo "Missing $(COUNTRY_OSM_PATH); run: make country" >&2; exit 1)
	@test -f "$(CITY_OSM_PBF)" || (echo "Missing $(CITY_OSM_PBF); run: make city" >&2; exit 1)
	@echo "OK country=$(COUNTRY_OSM_PATH)"
	@echo "OK city=$(CITY_OSM_PBF)"

# --- Pipeline (uses city PBF as OSM_PBF_PATH) ---

gpx: ## Fetch GPX tracks from [private] (parquet) into GPX_DIR; optional LAT/LON/RADIUS_KM filter
	uv run gpx-osm fetch-gpx $(if $(LAT),--lat $(LAT)) $(if $(LON),--lon $(LON)) $(if $(RADIUS_KM),--radius-km $(RADIUS_KM))

process: ## Parse/clean GPX → output/segments.*
	uv run gpx-osm process

cluster: ## Cluster overlapping segments
	uv run gpx-osm cluster

filter-missing: osm-check ## Keep only clusters poorly covered by OSM ways
	OSM_PBF_PATH=$(CITY_OSM_PBF) uv run gpx-osm filter-missing

name: osm-check ## POI names for missing clusters
	OSM_PBF_PATH=$(CITY_OSM_PBF) uv run gpx-osm name

extract: osm-check ## JOSM bundles (missing clusters only)
	OSM_PBF_PATH=$(CITY_OSM_PBF) uv run gpx-osm extract

pipeline: gpx city process cluster filter-missing name extract ## Full pipeline (fetch GPX + city clip + missing-path bundles)

clean: ## Remove processed data and outputs (keep raw gpx + city polys)
	rm -rf data/processed/* output/* clusters/* || true
	@echo "🧹 Cleaned processed/, output/, clusters/"

test: ## Run pytest with coverage
	uv run pytest

lint: ## Ruff + mypy
	uv run ruff check src tests
	uv run mypy src

# Entry point: full pipeline.
run: pipeline
