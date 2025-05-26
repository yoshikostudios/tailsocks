"""Tests for the logger module."""

import logging
import os
from unittest.mock import patch

from tailsocks.logger import setup_logger


def test_setup_logger_default():
    """Test setting up a logger with default settings."""
    logger = setup_logger("test_logger")

    assert logger.name == "test_logger"
    assert logger.level == logging.INFO
    assert len(logger.handlers) == 1
    assert isinstance(logger.handlers[0], logging.StreamHandler)


def test_setup_logger_custom_level():
    """Test setting up a logger with a custom level."""
    # First, make sure any existing logger with this name is removed
    if "test_logger" in logging.Logger.manager.loggerDict:
        del logging.Logger.manager.loggerDict["test_logger"]

    logger = setup_logger("test_logger", logging.DEBUG)

    assert logger.level == logging.DEBUG
    assert logger.handlers[0].level == logging.DEBUG


def test_setup_logger_env_level():
    """Test setting up a logger with level from environment variable."""
    with patch.dict(os.environ, {"TAILSOCKS_LOG_LEVEL": "ERROR"}):
        logger = setup_logger("test_logger")

        assert logger.level == logging.ERROR


def test_setup_logger_invalid_env_level():
    """Test setting up a logger with invalid level from environment variable."""
    with patch.dict(os.environ, {"TAILSOCKS_LOG_LEVEL": "INVALID_LEVEL"}):
        logger = setup_logger("test_logger")

        # Should fall back to INFO
        assert logger.level == logging.INFO


def test_setup_logger_existing_handlers():
    """Test setting up a logger that already has handlers."""
    # Create a logger with a handler
    logger_name = "test_existing_handlers"
    logger = logging.getLogger(logger_name)
    handler = logging.StreamHandler()
    logger.addHandler(handler)

    # Set up the logger again
    setup_logger(logger_name)

    # Should not add another handler
    assert len(logger.handlers) == 1
    assert logger.handlers[0] == handler
