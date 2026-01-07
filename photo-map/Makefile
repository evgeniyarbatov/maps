VENV_PATH := .venv

PYTHON := $(VENV_PATH)/bin/python
BLACK := $(VENV_PATH)/bin/black
FLAKE8 := $(VENV_PATH)/bin/flake8
PIP := $(VENV_PATH)/bin/pip

REQUIREMENTS := requirements.txt

SCRIPTS_DIR = scripts
PYTHON_FILES := $(shell find $(SCRIPTS_DIR) -name "*.py")

venv:
	@python3 -m venv $(VENV_PATH)

install: venv
	@$(PIP) install --disable-pip-version-check -q --upgrade pip
	@$(PIP) install --disable-pip-version-check -q -r $(REQUIREMENTS)

format:
	@if [ -n "$(PYTHON_FILES)" ]; then \
		$(BLACK) $(PYTHON_FILES); \
	else \
		echo "No Python files"; \
	fi

lint: format
	@if [ -n "$(PYTHON_FILES)" ]; then \
		$(FLAKE8) $(PYTHON_FILES); \
	else \
		echo "No Python files"; \
	fi

script:
	@$(PYTHON) $(SCRIPTS_DIR)/script.py

cleanvenv:
	@rm -rf $(VENV_PATH)