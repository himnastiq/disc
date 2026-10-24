"""Discovery Engine - Structured logging utilities (P2.12)."""

from __future__ import annotations

import logging
import sys
from typing import Any


def configure_logging(level: int = logging.INFO) -> None:
    """Configure root logging with consistent format and stdout handler."""
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    # Remove existing stream handlers to prevent duplicates
    root.handlers = [h for h in root.handlers if not isinstance(h, logging.StreamHandler)]
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Obtain a logger instance with structured event logging capabilities."""
    return logging.getLogger(f"engine.{name}")


def log_event(logger: logging.Logger, event: str, level: int = logging.INFO, **kwargs: Any) -> None:
    """Log a structured event with key-value attributes."""
    if kwargs:
        attrs = " ".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
        msg = f"{event} | {attrs}"
    else:
        msg = event
    logger.log(level, msg)
