"""Configuration du journal d'execution."""

from __future__ import annotations

import logging
import os
from pathlib import Path

_LOGGER_NAME = "dbreport"
_CONFIGURED = False


class _ConsoleFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return f"[{record.levelname.lower()}] {record.getMessage()}"


def setup_logging(verbose: int = 0) -> logging.Logger:
    """Configure et retourne le logger applicatif.

    :param verbose: 0 = INFO, 1 = DEBUG (console), >=2 = DEBUG (console + fichier).
    """

    global _CONFIGURED
    logger = logging.getLogger(_LOGGER_NAME)
    if _CONFIGURED:
        return logger

    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    console = logging.StreamHandler()
    console.setFormatter(_ConsoleFormatter())
    console.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.addHandler(console)

    log_file = os.environ.get("ORAREPORT_LOG_FILE")
    if verbose >= 2 and not log_file:
        log_file = str(Path(".dbreport") / "dbreport.log")

    if log_file:
        path = Path(log_file).expanduser()
        if path.parent and str(path.parent) not in ("", "."):
            path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(path, encoding="utf-8")
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
        handler.setLevel(logging.DEBUG)
        logger.addHandler(handler)

    _CONFIGURED = True
    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger(_LOGGER_NAME)
