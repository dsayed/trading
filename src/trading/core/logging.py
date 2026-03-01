"""Centralized logging configuration for the trading system."""

from __future__ import annotations

import logging
import os


def configure_logging(level: str | None = None) -> None:
    """Configure logging for the ``trading.*`` namespace.

    Args:
        level: Log level name (DEBUG, INFO, WARNING, …).
               Falls back to the ``TRADING_LOG_LEVEL`` env var, then INFO.
    """
    resolved = (level or os.environ.get("TRADING_LOG_LEVEL", "INFO")).upper()
    log_level = getattr(logging, resolved, logging.INFO)

    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(name)s %(levelname)s %(message)s",
            datefmt="%H:%M:%S",
        )
    )

    root = logging.getLogger("trading")
    root.setLevel(log_level)
    if not root.handlers:
        root.addHandler(handler)
