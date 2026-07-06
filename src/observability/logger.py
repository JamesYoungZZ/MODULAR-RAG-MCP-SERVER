"""Minimal stderr logger used before structured logging is implemented."""

from __future__ import annotations

import logging


def get_logger(name: str) -> logging.Logger:
    """Return a stderr logger with a stable project format."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger