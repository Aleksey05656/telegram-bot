# @file: Makefile
# @description: Development automation targets
# @dependencies: requirements.txt, scripts/verify.py
# @created: 2025-09-10

.PHONY: setup lint test smoke check fmt

PY ?= python
PIP ?= $(PY) -m pip

setup:
	$(PY) -m pip install -U pip
	if [ -f requirements.txt ]; then $(PIP) install -r requirements.txt; fi
	$(PIP) install "ruff==0.6.5" "black==24.8.0" "isort==5.13.2" "pre-commit>=3.7.0"
	pre-commit install -f || true
	@echo "Setup done."

lint:
	$(PY) -m ruff check . --fix --unsafe-fixes || true
	$(PY) -m isort .
	$(PY) -m black .
	# итоговый "гейт": показываем остаток после автофиксов
	$(PY) -m ruff check .
	$(PY) -m isort --check-only .
	$(PY) -m black --check .

fmt:
	ruff format .
	ruff check --fix .

test:
	pytest

smoke:
	python -m scripts.verify

check: lint test smoke
