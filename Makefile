# @file: Makefile
# @description: Development automation targets
# @dependencies: requirements.txt, scripts/verify.py
# @created: 2025-09-10

.PHONY: setup lint test smoke check fmt

PY ?= python

setup:
	pip install -r requirements.txt

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
