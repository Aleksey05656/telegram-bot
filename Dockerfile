# @file: Dockerfile
# @description: Multi-stage Dockerfile for production-ready Telegram bot deployment
# @created: 2025-09-21

FROM python:3.11-slim AS base
ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=100
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        build-essential \
        gcc \
        g++ \
        make \
        libpq-dev \
        libffi-dev \
        libssl-dev \
        libopenblas-dev \
        gfortran \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app

FROM base AS builder
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt constraints.txt ./
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt -c constraints.txt

FROM python:3.11-slim AS runtime
ARG APP_VERSION=0.0.0
ARG GIT_SHA=dev
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_VERSION=${APP_VERSION} \
    GIT_SHA=${GIT_SHA}
LABEL org.opencontainers.image.title="telegram-bot" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.revision="${GIT_SHA}"
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        libpq5 \
        libffi8 \
        libssl3 \
        libopenblas0-pthread \
        libstdc++6 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml requirements.txt constraints.txt ./
COPY config.py logger.py main.py data_processor.py ./
COPY app ./app
COPY core ./core
COPY database ./database
COPY metrics ./metrics
COPY ml ./ml
COPY services ./services
COPY storage ./storage
COPY telegram ./telegram
COPY workers ./workers
COPY scripts/__init__.py scripts/prestart.py scripts/entrypoint.sh ./scripts/

RUN chmod +x scripts/entrypoint.sh

RUN addgroup --system app \
    && adduser --system --ingroup app app
USER app

ENTRYPOINT ["./scripts/entrypoint.sh"]
