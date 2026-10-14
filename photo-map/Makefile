# Uses uv (https://docs.astral.sh/uv) for dependency management — uv sync creates/updates .venv; run commands via uv run, no manual activation.
PYTHON := uv run python

SCRIPTS_DIR = scripts
SITE_DIR = site

.DEFAULT_GOAL := help

.PHONY: help setup lock extract-photos run test

setup:
	@uv sync --all-packages
	@cd $(SITE_DIR) && npm ci

lock:
	@uv lock

extract-photos: setup
	@$(PYTHON) $(SCRIPTS_DIR)/extract_photo_locations.py \
	--input $(INPUT_DIR) \
	--output site/public/photos.json \
	--thumbs-dir site/public/thumbs

run: setup
	cd $(SITE_DIR) && npm run dev

test: setup
	@$(PYTHON) -m unittest discover -s tests
	cd $(SITE_DIR) && npm run test

help:
	@echo "setup          - uv sync + npm ci (site/)"
	@echo "run            - start the site dev server"
	@echo "test           - Python unit tests + site tests"
	@echo "lock           - uv lock"
	@echo "extract-photos - extract photo locations for the map"
