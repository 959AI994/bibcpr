"""Structured logging."""
from __future__ import annotations

import logging
import sys


def setup_logging(verbosity: int = 0) -> logging.Logger:
    """0 = WARNING, 1 = INFO, 2+ = DEBUG."""
    level = logging.WARNING
    if verbosity == 1:
        level = logging.INFO
    elif verbosity >= 2:
        level = logging.DEBUG
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("[cpr] %(levelname)s %(message)s"))
    logger = logging.getLogger("cpr")
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger("cpr")
