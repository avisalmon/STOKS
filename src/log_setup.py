"""
Logging configuration using loguru.

Sets up file + console logging with appropriate levels.
"""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger


def setup_logging(log_dir: Path | None = None, verbose: bool = False) -> Path | None:
    """
    Configure loguru for the application.

    Args:
        log_dir: Directory for log files. If None, no file logging.
        verbose: If True, show DEBUG on console. Otherwise INFO only.

    Returns:
        Path to the log file, or None if file logging is disabled.
    """
    # Remove default handler
    logger.remove()

    # Console: clean, minimal output
    console_level = "DEBUG" if verbose else "INFO"
    logger.add(
        sys.stderr,
        level=console_level,
        format=(
            "<green>{time:HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan> - "
            "<level>{message}</level>"
        ),
        colorize=True,
    )

    log_path = None

    # File: detailed logging
    if log_dir is not None:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "run.log"
        logger.add(
            str(log_path),
            level="DEBUG",
            format=(
                "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
                "{level: <8} | "
                "{name}:{function}:{line} - "
                "{message}"
            ),
            rotation="50 MB",
            retention="7 days",
            encoding="utf-8",
        )
        logger.debug(f"File logging enabled: {log_path}")

    return log_path
