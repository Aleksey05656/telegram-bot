# @file: Makefile
# @description: Development automation targets
# @dependencies: requirements.txt, scripts/verify.py
# @created: 2025-09-10

PY ?= python
PIP ?= $(PY) -m pip
PRECOMMIT ?= pre-commit
PORT ?= 8080

PRECOMMIT ?= pre-commit
PRE_COMMIT_HOME ?= .cache/pre-commit

.PHONY: setup deps-fix lint lint-soft lint-strict lint-app lint-changed fmt test test-fast test-smoke test-all coverage-html \
reports-gaps pre-commit-smart smoke pre-commit-offline check deps-lock deps-sync qa-deps safe-import api-selftest line-health-min \
docker-build docker-run alerts-validate warmup

IMAGE_NAME ?= telegram-bot
APP_VERSION ?= 0.0.0
GIT_SHA ?= $(shell git rev-parse --short HEAD)
IMAGE_TAG ?= $(APP_VERSION)-$(GIT_SHA)


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

lint: lint-soft

lint-soft:
	ruff check --isolated --select E9,F63,F7,F82 --target-version py310 --respect-gitignore \
		--extend-exclude migrations --extend-exclude alembic .

lint-strict:
	ruff check .
	black --check .
	isort --check-only .

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
	ruff check . --fix
	isort .
	black .

lint-changed:
	@files=$$(git diff --name-only --diff-filter=ACMRTUXB HEAD | grep -E "\.py$$" || true); \
	if [ -n "$$files" ]; then \
		echo "[lint-changed] targets: $$files"; \
		ruff check $$files --select E9,F63,F7,F82; \
	else \
		echo "[lint-changed] no python files changed"; \
	fi

test:
	pytest -q

test-fast:
	pytest -q -m "not slow and not e2e"

test-smoke:
	pytest -q -m bot_smoke

test-all:
	pytest --cov=./ --cov-report=xml --cov-report=term-missing && \
	python -m diagtools.coverage_enforce --total-min 80 --pkg-min workers=90 --pkg-min database=90 --pkg-min services=90 --pkg-min 'core/services'=90 --print-top 20 --summary-json reports/coverage_summary.json

coverage-html:
	pytest --cov=./ --cov-report=xml --cov-report=term-missing && \
	python -m diagtools.coverage_enforce --total-min 80 --pkg-min workers=90 --pkg-min database=90 --pkg-min services=90 --pkg-min 'core/services'=90 --print-top 20 --summary-json reports/coverage_summary.json && \
	pytest --cov=./ --cov-report=html

reports-gaps:
	python -m diagtools.coverage_gaps

pre-commit-smart:
	@echo "[pre-commit smart] trying online first, with fallback to offline config"
	@mkdir -p $(PRE_COMMIT_HOME)
	PRE_COMMIT_HOME=$(PRE_COMMIT_HOME) $(PY) scripts/run_precommit.py run --all-files || true

smoke: test-smoke

pre-commit-offline:
	@echo "[pre-commit offline] using .pre-commit-config.offline.yaml"
	$(PRECOMMIT) run --config .pre-commit-config.offline.yaml --all-files

check:
        @changed_files=$$(git diff --name-only --diff-filter=ACMRTUXB origin/main...HEAD | grep -E "\\.py$$" || true); \
        if [ -n "$$changed_files" ]; then \
                echo "[check] running style checks on: $$changed_files"; \
                $(PY) -m ruff check $$changed_files; \
                $(PY) -m black --check $$changed_files; \
                $(PY) -m isort --check-only $$changed_files; \
        else \
                echo "[check] no Python changes detected; skipping style checks"; \
        fi
        $(PY) -m pytest -q

deps-lock:
	$(PY) scripts/deps_lock.py

deps-sync:
	$(PIP) install --no-index --find-links wheels/ -r requirements.lock

qa-deps:
        USE_OFFLINE_STUBS=$${USE_OFFLINE_STUBS:-1} $(PY) -m tools.qa_deps_sync

safe-import:
	USE_OFFLINE_STUBS=1 QA_STUB_SSL=1 $(PY) -m tools.safe_import_sweep

api-selftest:
	USE_OFFLINE_STUBS=1 QA_STUB_SSL=1 $(PY) -m tools.api_selftest

# минимальный офлайн-аудит: стобы + (по возможности) колёса
line-health-min: qa-deps
	# статическая компиляция + критичный ruff уже покрыты make check; здесь запускаем импорт и api self-test
	$(PY) -m tools.offline_safe_import
	$(MAKE) api-selftest

docker-build:
	docker build --build-arg APP_VERSION=$(APP_VERSION) --build-arg GIT_SHA=$(GIT_SHA) \
                -t $(IMAGE_NAME):$(IMAGE_TAG) .

docker-run:
	docker run --rm \
	-e DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/app \
	-e REDIS_URL=redis://localhost:6379/0 \
	-e TELEGRAM_BOT_TOKEN=TEST_TELEGRAM_TOKEN \
	-e APP_VERSION=$(APP_VERSION) \
	-e GIT_SHA=$(GIT_SHA) \
	$(IMAGE_NAME):$(IMAGE_TAG)

alerts-validate:
	$(PY) tools/alerts_validate.py

warmup:
	curl -fsS http://localhost:$${PORT:-8000}/__smoke__/warmup || true
