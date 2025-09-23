# @file: logger.py
# Настройка логирования с использованием стандартного logging и JSON/logfmt форматов.
"""Application logging configuration with rotating file handlers."""
from __future__ import annotations

import json
import logging
import logging.handlers
import os
import sys
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from config import settings

os.environ.setdefault("PYTHONUNBUFFERED", "1")

LOG_DIR = Path(settings.LOG_DIR)
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "app.log"

_STANDARD_ATTRS = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
    "message",
}

_SENSITIVE_KEYWORDS = ("TOKEN", "KEY", "SECRET", "PASSWORD", "PWD")


def _mask_secret(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        if len(value) <= 4:
            return "***"
        return f"{value[:2]}***{value[-2:]}"
    return "***"


def _sanitize_mapping(mapping: Mapping[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in mapping.items():
        upper_key = key.upper()
        if isinstance(value, Mapping):
            sanitized[key] = _sanitize_mapping(value)
        elif any(token in upper_key for token in _SENSITIVE_KEYWORDS):
            sanitized[key] = _mask_secret(value)
        else:
            sanitized[key] = value
    return sanitized


class JsonFormatter(logging.Formatter):
    """Format records as JSON suitable for log aggregation."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and not key.startswith("_"):
                payload[key] = value
        return json.dumps(payload, ensure_ascii=False)


class LogfmtFormatter(logging.Formatter):
    """Format records using logfmt for stdout readability."""

    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage().replace("\n", "\\n")
        components = [
            f"time={datetime.utcfromtimestamp(record.created).isoformat()}Z",
            f"level={record.levelname.lower()}",
            f"logger={record.name}",
            f"message=\"{message}\"",
        ]
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and not key.startswith("_"):
                components.append(f"{key}={value}")
        if record.exc_info:
            components.append(f"exc=\"{self.formatException(record.exc_info)}\"")
        return " ".join(components)


def _configure_logger() -> logging.Logger:
    logger = logging.getLogger("amvera")
    logger.setLevel(getattr(logging, settings.LOG_LEVEL, logging.INFO))
    logger.propagate = False

    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE,
        maxBytes=int(10 * 1024 * 1024),
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(JsonFormatter())

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(LogfmtFormatter())

    logger.handlers.clear()
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logging.captureWarnings(True)
    return logger


class BindableLogger(logging.LoggerAdapter):
    """LoggerAdapter с поддержкой loguru-подобного bind."""

    def __init__(
        self,
        logger: logging.Logger,
        extra: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(logger, dict(extra or {}))

    def bind(self, **kwargs: Any) -> "BindableLogger":
        merged = dict(self.extra)
        merged.update(kwargs)
        return BindableLogger(self.logger, merged)

    def process(self, msg: str, kwargs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        extra = kwargs.setdefault("extra", {})
        extra.update(self.extra)
        if extra:
            kwargs["extra"] = _sanitize_mapping(extra)
        return msg, kwargs


logger = BindableLogger(_configure_logger())


__all__ = ["logger"]
