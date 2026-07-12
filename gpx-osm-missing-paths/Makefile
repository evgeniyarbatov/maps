.PHONY: help setup install ingest cluster enrich generate clean test lint osrm-prepare osrm-start

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup: ## Create venv with uv, install deps, pre-commit
	uv venv
	uv pip install -e ".[dev]"
	pre-commit install || true
	@echo "✅ Setup complete. Activate with: source .venv/bin/activate (or uv run ...)"

install: ## Install/update deps only
	uv pip install -e ".[dev]"

ingest: ## Process all GPX in ./gpx/ into data/processed/tracks.parquet (idempotent)
	uv run python -m gpx_osm_missing_paths.cli ingest

cluster: ## Dedupe + cluster overlapping tracks, assign cluster_ids, save clusters metadata
	uv run python -m gpx_osm_missing_paths.cli cluster

enrich: ## Add human-readable names using POIs from OSM within 50m buffer of each cluster
	uv run python -m gpx_osm_missing_paths.cli enrich

generate: ## For each interesting cluster: create 50m buffer .osm extract (if OSM_PBF set), bundle GPX, geojson, metadata.json ready for JOSM
	uv run python -m gpx_osm_missing_paths.cli generate-outputs

pipeline: ingest cluster enrich generate ## Run the full pipeline end-to-end

clean: ## Remove processed data and outputs (keep raw gpx)
	rm -rf data/processed/* output/* || true
	@echo "🧹 Cleaned processed/ and output/"

test: ## Run pytest with coverage
	uv run pytest

lint: ## Ruff + mypy
	uv run ruff check src tests
	uv run mypy src

osrm-prepare: ## Prepare OSRM data (place your region.osm.pbf in data/osrm/ first). Uses foot profile.
	@echo "Make sure data/osrm/region.osm.pbf exists (e.g. HCMC or Vietnam extract from Geofabrik/BBBike)"
	docker compose run --rm osrm osrm-extract -p /opt/foot.lua /data/region.osm.pbf
	docker compose run --rm osrm osrm-contract /data/region.osrm
	@echo "✅ OSRM prepared. Now you can: docker compose up -d osrm  (or make osrm-start)"

osrm-start: ## Start OSRM routed container (after prepare)
	docker compose up -d osrm
	@echo "OSRM match API available at http://localhost:5000/match/v1/foot/..."

osrm-stop:
	docker compose down osrm
