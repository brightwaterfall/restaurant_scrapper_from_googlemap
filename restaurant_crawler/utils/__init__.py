"""Shared utilities."""

from restaurant_crawler.utils.deduplication import Deduplicator
from restaurant_crawler.utils.normalize import normalize_address, normalize_name, make_fingerprint
from restaurant_crawler.utils.logging import setup_logging, get_logger

__all__ = [
    "Deduplicator",
    "normalize_address",
    "normalize_name",
    "make_fingerprint",
    "setup_logging",
    "get_logger",
]
