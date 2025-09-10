# @file: Makefile
# @description: Development automation targets
# @dependencies: requirements.txt, scripts/verify.py
# @created: 2025-09-10

.PHONY: setup lint test smoke check fmt

setup:
	pip install -r requirements.txt

lint:
	ruff check .
	mypy .

fmt:
	ruff format .
	ruff check --fix .

test:
	pytest

smoke:
	python -m scripts.verify

check: lint test smoke
