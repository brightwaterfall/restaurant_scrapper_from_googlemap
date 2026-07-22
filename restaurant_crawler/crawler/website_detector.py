"""Detect whether a website is static HTML or requires a JS browser."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from bs4 import BeautifulSoup

from restaurant_crawler.utils.logging import get_logger

logger = get_logger()


class WebsiteType(str, Enum):
    STATIC = "static"
    DYNAMIC = "dynamic"
    UNKNOWN = "unknown"


@dataclass
class DetectionResult:
    website_type: WebsiteType
    reason: str
    has_infinite_scroll: bool = False
    has_pagination: bool = False
    menu_links: list[str] | None = None


SPA_MARKERS = (
    "id=\"__next\"",
    "id=\"root\"",
    "ng-app",
    "data-reactroot",
    "window.__INITIAL_STATE__",
    "webpackJsonp",
    "vue-app",
)

FRAMEWORK_SCRIPTS = re.compile(
    r"(react|vue|angular|nuxt|next\.js|gatsby|ember)",
    re.I,
)

INFINITE_SCROLL_MARKERS = re.compile(
    r"(infinite[-_ ]?scroll|load[-_ ]?more|IntersectionObserver|lazy[-_ ]?load)",
    re.I,
)

PAGINATION_MARKERS = re.compile(
    r"(pagination|page=\d|rel=[\"']next[\"']|class=[\"'][^\"']*pager)",
    re.I,
)

MENU_HREF = re.compile(
    r"(cardapio|cardápio|menu|carta|food-menu|/menu|/cardapio)",
    re.I,
)


class WebsiteDetector:
    def detect(self, html: str, url: str | None = None) -> DetectionResult:
        if not html or len(html.strip()) < 50:
            return DetectionResult(WebsiteType.UNKNOWN, "empty_html")

        lower = html.lower()
        soup = BeautifulSoup(html, "lxml")
        text_len = len(soup.get_text(" ", strip=True))
        script_count = len(soup.find_all("script"))

        spa_hits = [m for m in SPA_MARKERS if m.lower() in lower]
        framework = bool(FRAMEWORK_SCRIPTS.search(html))
        infinite = bool(INFINITE_SCROLL_MARKERS.search(html))
        pagination = bool(PAGINATION_MARKERS.search(html)) or bool(
            soup.select("a[rel='next'], .pagination a, .pager a")
        )

        menu_links: list[str] = []
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            label = anchor.get_text(" ", strip=True)
            if MENU_HREF.search(href) or MENU_HREF.search(label or ""):
                menu_links.append(href)

        # Heuristic: little text + many scripts / SPA markers => dynamic
        if spa_hits or (framework and text_len < 800 and script_count >= 5):
            return DetectionResult(
                WebsiteType.DYNAMIC,
                reason="spa_or_framework",
                has_infinite_scroll=infinite,
                has_pagination=pagination,
                menu_links=menu_links,
            )

        if text_len < 200 and script_count >= 8:
            return DetectionResult(
                WebsiteType.DYNAMIC,
                reason="low_text_high_scripts",
                has_infinite_scroll=infinite,
                has_pagination=pagination,
                menu_links=menu_links,
            )

        return DetectionResult(
            WebsiteType.STATIC,
            reason="static_html",
            has_infinite_scroll=infinite,
            has_pagination=pagination,
            menu_links=menu_links,
        )
