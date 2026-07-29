"""
test_logging_setup.py — Tests for logging configuration and utilities.
"""
import logging
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest
from gaming_tweaks.logging_setup import (
    setup_logging, get_logger, OperationContext, _logger_cache,
)


def _cleanup_logger(name):
    logger = logging.getLogger(name)
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)
    _logger_cache.pop(name, None)


class TestLoggingSetup:
    def setup_method(self):
        _logger_cache.clear()

    def test_setup_logging_basic(self):
        try:
            logger = setup_logging("test_basic", enable_file=False, enable_console=False)
            assert logger.name == "test_basic"
            assert logger.level == logging.INFO
        finally:
            _cleanup_logger("test_basic")

    def test_setup_logging_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir)
            try:
                logger = setup_logging(
                    "test_file", log_dir=log_dir, enable_console=False)
                assert logger.name == "test_file"
                log_files = list(log_dir.glob("test_file_*.log"))
                assert len(log_files) >= 1
            finally:
                _cleanup_logger("test_file")

    def test_setup_logging_returns_cached(self):
        try:
            logger1 = setup_logging("test_cache", enable_file=False, enable_console=False)
            logger2 = setup_logging("test_cache", enable_file=False, enable_console=False)
            assert logger1 is logger2
        finally:
            _cleanup_logger("test_cache")

    def test_get_logger_creates(self):
        logger = get_logger("test_get")
        assert isinstance(logger, logging.Logger)

    def test_get_logger_default(self):
        logger = get_logger()
        assert logger.name == "gaming_tweaks"

    def test_logger_levels(self):
        try:
            logger = setup_logging("test_levels", level=logging.DEBUG,
                                   enable_file=False, enable_console=False)
            assert logger.level == logging.DEBUG
        finally:
            _cleanup_logger("test_levels")


class TestOperationContext:
    def test_context_success(self):
        try:
            logger = setup_logging("test_ctx", enable_file=False, enable_console=False)
            with OperationContext(logger, "test_operation", key="val") as ctx:
                assert ctx.operation == "test_operation"
                assert ctx.metadata == {"key": "val"}
            assert ctx._start_time is not None
        finally:
            _cleanup_logger("test_ctx")

    def test_context_exception(self):
        try:
            logger = setup_logging("test_ctx_err", enable_file=False, enable_console=False)
            try:
                with OperationContext(logger, "failing_op") as ctx:
                    raise ValueError("test error")
            except ValueError:
                pass
            assert ctx._start_time is not None
        finally:
            _cleanup_logger("test_ctx_err")
