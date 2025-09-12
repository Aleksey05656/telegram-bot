# @file: Makefile
# @description: Development automation targets
# @dependencies: requirements.txt, scripts/verify.py
# @created: 2025-09-10

.PHONY: setup lint test smoke check fmt pre-commit-smart

PY ?= python
PIP ?= $(PY) -m pip

PRECOMMIT ?= pre-commit
PRE_COMMIT_HOME ?= .cache/pre-commit


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

lint-app:
	$(PY) scripts/syntax_partition.py
	@if [ -s .lint_targets_app ]; then \
		count=`wc -l < .lint_targets_app`; \
		echo "[lint-app] targets: $$count files"; \
		$(PY) -m ruff check --fix --unsafe-fixes `cat .lint_targets_app`; \
		$(PY) -m isort `cat .lint_targets_app`; \
		$(PY) -m black --force-exclude "$(BLACK_EXCLUDE)" `cat .lint_targets_app`; \
		$(PY) -m ruff check `cat .lint_targets_app`; \
		$(PY) -m isort --check-only `cat .lint_targets_app`; \
		$(PY) -m black --force-exclude "$(BLACK_EXCLUDE)" --check `cat .lint_targets_app`; \
	else \
		echo "[lint-app] no parseable targets found (skipped)"; \
	fi

fmt:
	ruff format app tests
	ruff check --fix app tests

test:
	pytest

pre-commit-smart:
	@echo "[pre-commit smart] trying online first, with fallback to offline config"
	@mkdir -p $(PRE_COMMIT_HOME)
	PRE_COMMIT_HOME=$(PRE_COMMIT_HOME) $(PY) scripts/run_precommit.py run --all-files || true

smoke:
	python -m scripts.verify

check: lint test smoke
