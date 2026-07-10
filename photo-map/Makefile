# Uses uv (https://docs.astral.sh/uv) for dependency management — uv sync creates/updates .venv; run commands via uv run, no manual activation.
PYTHON := uv run python

SCRIPTS_DIR = scripts
SITE_DIR = site

default: run

.PHONY: install lock extract-photos run test clean

install:
	@uv sync

lock:
	@uv lock

extract-photos: install
	@$(PYTHON) $(SCRIPTS_DIR)/extract_photo_locations.py \
	--input $(INPUT_DIR) \
	--output site/public/photos.json \
	--thumbs-dir site/public/thumbs

run:
	cd $(SITE_DIR) && npm run dev

test: install
	@$(PYTHON) -m unittest discover -s tests
	cd $(SITE_DIR) && npm run test

clean:
	@rm -rf \
	site/public/thumbs \
	site/public/photos \
	site/public/photos.json

