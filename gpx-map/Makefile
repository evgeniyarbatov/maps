# Uses uv (https://docs.astral.sh/uv) for dependency management — uv sync creates/updates .venv; run commands via uv run, no manual activation.
DATA_ROOT ?= $(HOME)/Documents/data
REPO_NAME := $(notdir $(CURDIR))
DATA_DIR  ?= $(DATA_ROOT)/$(REPO_NAME)

PYTHON := uv run python

.DEFAULT_GOAL := help

.PHONY: help setup lock lab run test video

setup:
	@uv sync --all-packages
	@npm install

lock:
	@uv lock

lab: setup
	@$(PYTHON) -m jupyter lab

run: setup
	@npm run start

video:
	@test -n "$(GPX)" || (echo "usage: make video GPX=/path/to/track.gpx" >&2; exit 2)
	@$(MAKE) setup
	@DATA_DIR="$(DATA_DIR)" ./scripts/make_video.sh "$(GPX)"

test:
	@echo "no tests defined" >&2; exit 1

help:
	@echo "setup - uv sync + npm install"
	@echo "run   - start the map app"
	@echo "test  - no tests defined (fails)"
	@echo "lock  - uv lock"
	@echo "lab   - open Jupyter Lab"
	@echo "video - render a video for GPX=..."
