"""Loguru-based logging setup."""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

_CONFIGURED = False


def setup_logging(
    log_dir: str | Path,
    level: str = "INFO",
    rotation: str = "50 MB",
    retention: str = "30 days",
) -> None:
    global _CONFIGURED
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    if _CONFIGURED:
        return

    logger.remove()
    logger.add(
        sys.stderr,
        level=level.upper(),
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan> - "
            "<level>{message}</level>"
        ),
        colorize=True,
    )
    logger.add(
        log_path / "crawler_{time:YYYY-MM-DD}.log",
        level=level.upper(),
        rotation=rotation,
        retention=retention,
        encoding="utf-8",
        enqueue=True,
        backtrace=True,
        diagnose=False,
    )
    logger.add(
        log_path / "errors_{time:YYYY-MM-DD}.log",
        level="ERROR",
        rotation=rotation,
        retention=retention,
        encoding="utf-8",
        enqueue=True,
    )
    _CONFIGURED = True


def get_logger():
    return logger
