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
	# основной путь: по constraints
	-$(PIP) install -r requirements.txt -c constraints.txt --prefer-binary --retries 2 --timeout 60
	-$(PIP) install -c constraints.txt --prefer-binary --retries 2 --timeout 60 ruff black isort pre-commit pytest pytest-asyncio || true
	# fallback при блокировке прокси: непинованные, но бинарные, чтобы избежать сборки из исходников
	@if ! $(PY) -c "import numpy, pandas" >/dev/null 2>&1; then \
	echo "Fallback install (unpinned, prefer-binary)"; \
	$(PIP) install --only-binary=:all: --prefer-binary numpy pandas scipy pyarrow || true; \
	$(PIP) install ruff black isort pre-commit pytest pytest-asyncio || true; \
	fi
	pre-commit install -f || true
	@echo "Setup done."
	
deps-fix:
# Полный цикл переустановки бинарной четвёрки
	-$(PIP) uninstall -y pandas numpy scipy pyarrow || true
	$(PIP) install -c constraints.txt --only-binary=:all: --prefer-binary numpy pandas scipy pyarrow
	@echo "Deps fixed."
	
lint:
	@echo "LINT_STRICT=$${LINT_STRICT:-0}"
	@if [ "$${LINT_STRICT:-0}" = "1" ]; then \
	        echo "[strict lint] ruff fix + isort + black check"; \
	        $(PY) -m ruff check app tests --fix --unsafe-fixes; \
	        $(PY) -m isort .; \
	        $(PY) -m black --force-exclude "$(BLACK_EXCLUDE)" ; \
	        $(PY) -m ruff check app tests; \
	        $(PY) -m isort --check-only .; \
	        $(PY) -m black --force-exclude "$(BLACK_EXCLUDE)" --check .; \
	else \
	        echo "[lenient lint] ruff fix + isort + black (без фейла)"; \
	        $(PY) -m ruff check app tests --fix --unsafe-fixes || true; \
	        $(PY) -m isort . || true; \
	        $(PY) -m black --force-exclude "$(BLACK_EXCLUDE)" . || true; \
	        # отчёт остатка, но не фейлим сборку: \
	        $(PY) -m ruff check app tests || true; \
	fi

fmt:
	ruff format app tests
	ruff check --fix app tests

test:
	pytest

smoke:
	python -m scripts.verify

check: lint test smoke
