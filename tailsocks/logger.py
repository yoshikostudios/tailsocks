"""
Logging functionality for tailsocks.

Copyright (c) 2025 Yoshiko Studios LLC
Licensed under the MIT License
"""

import logging
import os
import sys
from typing import Optional


def setup_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """
    Set up and configure a logger.

    Args:
        name: The name of the logger
        level: The logging level (defaults to INFO or value from TAILSOCKS_LOG_LEVEL env var)

    Returns:
        A configured logger instance
    """
    # Get log level from environment or use INFO as default
    if level is None:
        env_level = os.environ.get("TAILSOCKS_LOG_LEVEL", "INFO").upper()
        level = getattr(logging, env_level, logging.INFO)

    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Create console handler if no handlers exist
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        # Set handler level to match logger level
        handler.setLevel(level)

        # Create formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)

        # Add handler to logger
        logger.addHandler(handler)

    return logger
