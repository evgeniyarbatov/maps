VENV_PATH := .venv

PYTHON := $(VENV_PATH)/bin/python
PIP := $(VENV_PATH)/bin/pip

REQUIREMENTS := requirements.txt

SCRIPTS_DIR = scripts
SITE_DIR = site

default: run

venv:
	@python3 -m venv $(VENV_PATH)

install: venv
	@$(PIP) install --disable-pip-version-check -q --upgrade pip
	@$(PIP) install --disable-pip-version-check -q -r $(REQUIREMENTS)

run:
	cd $(SITE_DIR) && npm run dev

extract-photos:
	@$(PYTHON) $(SCRIPTS_DIR)/extract_photo_locations.py --input $(INPUT_DIR) --output site/public/photos.json --thumbs-dir site/public/thumbs

cleanvenv:
	@rm -rf $(VENV_PATH)
