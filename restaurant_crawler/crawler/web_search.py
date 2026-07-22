"""Public web search helpers (DuckDuckGo HTML — no API key required)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, unquote, urlparse

from bs4 import BeautifulSoup

from restaurant_crawler.utils.http_client import HttpClient
from restaurant_crawler.utils.logging import get_logger

logger = get_logger()

DDG_HTML = "https://html.duckduckgo.com/html/"
DDG_LITE = "https://lite.duckduckgo.com/lite/"


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str = ""


class WebSearcher:
    """Search the public web for restaurant presence."""

    def __init__(self, http: HttpClient) -> None:
        self.http = http

    async def search(self, query: str, *, max_results: int = 10) -> list[SearchResult]:
        results = await self._search_ddg_html(query, max_results=max_results)
        if results:
            return results
        return await self._search_ddg_lite(query, max_results=max_results)

    async def _search_ddg_html(self, query: str, *, max_results: int) -> list[SearchResult]:
        response = await self.http.post_form(
            DDG_HTML,
            {"q": query, "b": ""},
            check_robots=True,
            timeout=45,
        )
        if response is None or response.status_code >= 400:
            # Fallback GET
            from urllib.parse import quote_plus

            response = await self.http.get(
                f"{DDG_HTML}?q={quote_plus(query)}",
                check_robots=True,
            )
        if response is None or response.status_code >= 400:
            logger.warning("DuckDuckGo HTML search failed for: {}", query)
            return []
        return self._parse_ddg_html(response.text, max_results=max_results)

    async def _search_ddg_lite(self, query: str, *, max_results: int) -> list[SearchResult]:
        from urllib.parse import quote_plus

        response = await self.http.get(
            f"{DDG_LITE}?q={quote_plus(query)}",
            check_robots=True,
        )
        if response is None or response.status_code >= 400:
            return []
        return self._parse_ddg_lite(response.text, max_results=max_results)

    def _parse_ddg_html(self, html: str, *, max_results: int) -> list[SearchResult]:
        soup = BeautifulSoup(html, "lxml")
        results: list[SearchResult] = []
        for result in soup.select(".result, .web-result, .results_links"):
            anchor = result.select_one("a.result__a, a.result-link, a[href]")
            if not anchor or not anchor.get("href"):
                continue
            url = self._unwrap_ddg_url(anchor["href"])
            if not url or not url.startswith("http"):
                continue
            title = anchor.get_text(" ", strip=True)
            snippet_node = result.select_one(".result__snippet, .result-snippet, td.result-snippet")
            snippet = snippet_node.get_text(" ", strip=True) if snippet_node else ""
            results.append(SearchResult(title=title, url=url, snippet=snippet))
            if len(results) >= max_results:
                break
        return results

    def _parse_ddg_lite(self, html: str, *, max_results: int) -> list[SearchResult]:
        soup = BeautifulSoup(html, "lxml")
        results: list[SearchResult] = []
        for anchor in soup.select("a[href]"):
            href = anchor.get("href", "")
            if not href.startswith("http"):
                continue
            if any(x in href for x in ("duckduckgo.com", "javascript:")):
                continue
            title = anchor.get_text(" ", strip=True)
            if not title or len(title) < 3:
                continue
            results.append(SearchResult(title=title, url=href, snippet=""))
            if len(results) >= max_results:
                break
        return results

    @staticmethod
    def _unwrap_ddg_url(href: str) -> str:
        """DuckDuckGo often wraps destinations in /l/?uddg=..."""
        if "uddg=" in href:
            parsed = urlparse(href)
            qs = parse_qs(parsed.query)
            if "uddg" in qs:
                return unquote(qs["uddg"][0])
        if href.startswith("//duckduckgo.com/l/?") or "/l/?" in href:
            parsed = urlparse(href if "://" in href else f"https:{href}")
            qs = parse_qs(parsed.query)
            if "uddg" in qs:
                return unquote(qs["uddg"][0])
        return href


# Domains treated as social / delivery / directories — not official websites
NON_WEBSITE_HOSTS = re.compile(
    r"(facebook\.com|fb\.com|instagram\.com|ifood\.com\.br|rappi\.com|"
    r"ubereats\.com|aiqfome\.com|deliverymuch\.com\.br|tripadvisor\.|"
    r"yelp\.|linkedin\.|twitter\.com|x\.com|tiktok\.com|youtube\.com|"
    r"maps\.google\.|google\.com/maps|goo\.gl/maps|duckduckgo\.com|"
    r"wikipedia\.org|wikidata\.org)",
    re.I,
)

SOCIAL_HOSTS = {
    "facebook": re.compile(r"(facebook\.com|fb\.com)", re.I),
    "instagram": re.compile(r"instagram\.com", re.I),
}

DELIVERY_HOSTS = {
    "iFood": re.compile(r"ifood\.com\.br", re.I),
    "Rappi": re.compile(r"rappi\.com", re.I),
    "Uber Eats": re.compile(r"ubereats\.com|uber\.com/.+eats", re.I),
    "Aiqfome": re.compile(r"aiqfome\.com", re.I),
    "Delivery Much": re.compile(r"deliverymuch\.com\.br", re.I),
}


def classify_url(url: str) -> str:
    """Return website | facebook | instagram | delivery | other."""
    host = urlparse(url).netloc.lower()
    path = url
    for key, pattern in SOCIAL_HOSTS.items():
        if pattern.search(host) or pattern.search(path):
            return key
    for name, pattern in DELIVERY_HOSTS.items():
        if pattern.search(host) or pattern.search(path):
            return "delivery"
    if NON_WEBSITE_HOSTS.search(host):
        return "other"
    return "website"


def ensure_http_url(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    if value.startswith(("http://", "https://")):
        return value
    if re.match(r"^[\w.-]+\.[a-z]{2,}(/.*)?$", value, re.I):
        return f"https://{value}"
    return value
