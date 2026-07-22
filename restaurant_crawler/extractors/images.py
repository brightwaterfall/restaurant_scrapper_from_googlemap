"""High-resolution image URL discovery from HTML."""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

THUMB_HINTS = re.compile(
    r"(thumb|thumbnail|tiny|small|\d{2,3}x\d{2,3}|[-_/]sm[-_/]|[-_/]xs[-_/])",
    re.I,
)
IMAGE_EXT = re.compile(r"\.(jpe?g|png|webp|gif|avif)(\?|$)", re.I)
SIZE_IN_URL = re.compile(r"/(\d{2,4})/(\d{2,4})/")


def _upgrade_url(url: str) -> str:
    """Attempt to convert common thumbnail URL patterns to larger variants."""
    upgraded = url
    replacements = [
        ("/thumb/", "/"),
        ("/thumbnail/", "/"),
        ("_thumb", ""),
        ("_small", ""),
        ("-small", ""),
        ("_150x150", ""),
        ("_200x200", ""),
        ("w=150", "w=1600"),
        ("w=300", "w=1600"),
        ("h=150", "h=1600"),
        ("=s96", "=s1600"),
        ("=s128", "=s1600"),
        ("=s256", "=s1600"),
        ("=s512", "=s1600"),
    ]
    for old, new in replacements:
        if old in upgraded:
            upgraded = upgraded.replace(old, new)
    return upgraded


def extract_image_urls(soup: BeautifulSoup, base_url: str, limit: int = 40) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()

    def add(candidate: str | None, prefer_original: bool = True) -> None:
        if not candidate:
            return
        absolute = urljoin(base_url, candidate.strip())
        if absolute.startswith("data:"):
            return
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"}:
            return
        if prefer_original:
            absolute = _upgrade_url(absolute)
        key = absolute.split("?")[0]
        if key in seen:
            return
        seen.add(key)
        urls.append(absolute)

    # Open Graph / Twitter
    for prop in ("og:image", "og:image:secure_url", "twitter:image"):
        tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
        if tag and tag.get("content"):
            add(tag["content"])

    for img in soup.find_all("img"):
        candidates = [
            img.get("src"),
            img.get("data-src"),
            img.get("data-original"),
            img.get("data-lazy"),
            img.get("data-full"),
            img.get("data-large"),
        ]
        srcset = img.get("srcset") or img.get("data-srcset")
        if srcset:
            # pick largest candidate from srcset
            parts = [p.strip().split(" ")[0] for p in srcset.split(",") if p.strip()]
            candidates.extend(parts)
        for candidate in candidates:
            add(candidate)

    # Background images in style attributes
    for node in soup.find_all(style=True):
        match = re.search(r"url\(['\"]?(.*?)['\"]?\)", node["style"])
        if match:
            add(match.group(1))

    # Prefer non-thumbnails first
    ranked = sorted(
        urls,
        key=lambda u: (1 if THUMB_HINTS.search(u) else 0, len(u)),
    )
    filtered = [u for u in ranked if IMAGE_EXT.search(u) or "image" in u.lower()]
    return (filtered or ranked)[:limit]


def is_likely_thumbnail(url: str, width: int | None = None, height: int | None = None) -> bool:
    if THUMB_HINTS.search(url):
        return True
    if width is not None and height is not None and (width < 200 or height < 200):
        return True
    return False
