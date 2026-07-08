VENV_PATH := .venv

PYTHON := $(VENV_PATH)/bin/python
PIP := $(VENV_PATH)/bin/pip

REQUIREMENTS := requirements.txt

SCRIPTS_DIR = scripts
SITE_DIR = site

default: run

venv:
	@uv venv $(VENV_PATH)

install: venv
	@uv pip install -q -r $(REQUIREMENTS)

extract-photos:
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

cleanvenv:
	@rm -rf $(VENV_PATH)
