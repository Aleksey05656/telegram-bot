# @file: Makefile
# @description: Development automation targets
# @dependencies: requirements.txt, scripts/verify.py
# @created: 2025-09-10

.PHONY: setup lint test smoke check fmt

PY ?= python
PIP ?= $(PY) -m pip

BLACK_EXCLUDE = (^(legacy|experiments|notebooks|scripts/migrations)/|$(BLACK_EXTRA))
-include .env.blackexclude
BLACK_EXTRA ?=

setup:
	$(PY) -m pip install -U pip
	if [ -f requirements.txt ]; then $(PIP) install -r requirements.txt || true; fi
	# Пытаемся установить пинованные версии; если прокси блокирует — откатываемся на непинованные
	-$(PIP) install "ruff==0.6.5" "black==24.8.0" "isort==5.13.2" "pre-commit>=3.7.0" --retries 2 --timeout 60
	@if ! $(PY) -c "import ruff, black, isort, sys" >/dev/null 2>&1; then \
		echo "Pinned install failed or partial — installing fallback (unpinned)"; \
		$(PIP) install ruff black isort pre-commit --retries 2 --timeout 60 || true; \
	fi
	pre-commit install -f || true
	@echo "Setup done."

lint:
	$(PY) -m ruff check app tests --fix --unsafe-fixes || true
	$(PY) -m isort .
	$(PY) -m black --force-exclude "$(BLACK_EXCLUDE)" .
	# итоговый "гейт": показываем остаток после автофиксов
	$(PY) -m ruff check app tests
	$(PY) -m isort --check-only .
	$(PY) -m black --force-exclude "$(BLACK_EXCLUDE)" --check .

fmt:
	ruff format app tests
	ruff check --fix app tests

test:
	pytest

smoke:
	python -m scripts.verify

check: lint test smoke
