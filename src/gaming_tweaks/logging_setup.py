"""
logging_setup.py — Production-grade logging configuration with multiple handlers,
log rotation, and contextual logging for gaming_tweaks operations.

Provides structured logging with operation tracking, performance metrics,
and error context for debugging and monitoring.
"""

import logging
import logging.handlers
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

_logger_cache: dict[str, logging.Logger] = {}

LOG_FORMAT_DETAILED = (
    "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s"
)
LOG_FORMAT_CONSOLE = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_FORMAT_JSON = (
    '{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s",'
    '"msg":"%(message)s"}'
)

DEFAULT_LOG_DIR = Path(os.environ.get("GAMING_TWEAKS_LOG_DIR", "logs"))
MAX_LOG_SIZE = 10 * 1024 * 1024
BACKUP_COUNT = 5


def setup_logging(
    name: str = "gaming_tweaks",
    log_dir: Optional[Path] = None,
    level: int = logging.INFO,
    enable_file: bool = True,
    enable_console: bool = True,
    json_format: bool = False,
    capture_warnings: bool = True,
) -> logging.Logger:
    if name in _logger_cache:
        return _logger_cache[name]

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False

    if not logger.handlers:
        fmt = LOG_FORMAT_JSON if json_format else LOG_FORMAT_DETAILED

        if enable_file:
            log_path = log_dir or DEFAULT_LOG_DIR
            log_path.mkdir(parents=True, exist_ok=True)
            file_handler = logging.handlers.RotatingFileHandler(
                log_path / f"{name}_{datetime.now():%Y%m%d}.log",
                maxBytes=MAX_LOG_SIZE,
                backupCount=BACKUP_COUNT,
                encoding="utf-8",
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(logging.Formatter(fmt))
            logger.addHandler(file_handler)

            error_handler = logging.handlers.RotatingFileHandler(
                log_path / f"{name}_errors.log",
                maxBytes=MAX_LOG_SIZE,
                backupCount=BACKUP_COUNT,
                encoding="utf-8",
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(logging.Formatter(fmt))
            logger.addHandler(error_handler)

        if enable_console:
            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setLevel(level)
            console_fmt = LOG_FORMAT_JSON if json_format else LOG_FORMAT_CONSOLE
            console_handler.setFormatter(logging.Formatter(console_fmt))
            logger.addHandler(console_handler)

    if capture_warnings:
        logging.captureWarnings(True)

    _logger_cache[name] = logger
    return logger


def get_logger(name: str = "gaming_tweaks") -> logging.Logger:
    if name in _logger_cache:
        return _logger_cache[name]
    return logging.getLogger(name)


class OperationContext:
    def __init__(self, logger: logging.Logger, operation: str, **metadata):
        self.logger = logger
        self.operation = operation
        self.metadata = metadata
        self._start_time: Optional[datetime] = None

    def __enter__(self):
        self._start_time = datetime.now()
        self.logger.info(f"START: {self.operation} | meta={self.metadata}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = (datetime.now() - self._start_time).total_seconds()
        if exc_type:
            self.logger.error(
                f"FAIL: {self.operation} | elapsed={elapsed:.3f}s | "
                f"error={exc_type.__name__}: {exc_val}"
            )
        else:
            self.logger.info(
                f"DONE: {self.operation} | elapsed={elapsed:.3f}s"
            )
        return False
