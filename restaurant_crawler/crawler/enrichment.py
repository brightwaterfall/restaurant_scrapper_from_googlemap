"""Enrich restaurants by searching public web / social / delivery listings."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote_plus, urlparse

from rapidfuzz import fuzz

from restaurant_crawler.config.settings import Settings
from restaurant_crawler.crawler.web_search import (
    DELIVERY_HOSTS,
    SearchResult,
    WebSearcher,
    classify_url,
    ensure_http_url,
)
from restaurant_crawler.extractors.website_extractor import WebsiteExtractor
from restaurant_crawler.models.restaurant import Restaurant
from restaurant_crawler.models.source import Source
from restaurant_crawler.utils.http_client import HttpClient
from restaurant_crawler.utils.logging import get_logger
from restaurant_crawler.utils.normalize import normalize_name, normalize_phone

logger = get_logger()

PHONE_RE = re.compile(
    r"(?:\+?55\s*)?(?:\(?\d{2}\)?\s*)?(?:9?\d{4})[-\s]?\d{4}",
)
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


@dataclass
class EnrichmentResult:
    restaurant: Restaurant
    sources: list[Source] = field(default_factory=list)
    found_website: bool = False
    found_social: bool = False
    found_delivery: bool = False
    search_hits: int = 0
    queries: list[str] = field(default_factory=list)


class RestaurantEnricher:
    """Find website / social / phone / delivery links via public web search."""

    def __init__(self, settings: Settings, http: HttpClient) -> None:
        self.settings = settings
        self.http = http
        self.searcher = WebSearcher(http)
        self.extractor = WebsiteExtractor()

    def needs_enrichment(self, restaurant: Restaurant) -> bool:
        missing_core = not restaurant.website or not restaurant.phone
        missing_social = not restaurant.facebook and not restaurant.instagram
        missing_delivery = not restaurant.delivery_platforms
        return bool(missing_core or missing_social or missing_delivery)

    async def enrich(self, restaurant: Restaurant) -> EnrichmentResult:
        result = EnrichmentResult(restaurant=restaurant)
        if not self.settings.enrichment.enabled:
            return result

        restaurant.website = ensure_http_url(restaurant.website)
        self._reclassify_misplaced_website(restaurant)
        queries = self._build_queries(restaurant)
        result.queries = queries

        all_hits: list[SearchResult] = []
        seen_urls: set[str] = set()
        for query in queries:
            hits = await self.searcher.search(
                query, max_results=self.settings.enrichment.max_results_per_query
            )
            for hit in hits:
                if hit.url in seen_urls:
                    continue
                if not self._result_matches_restaurant(restaurant, hit):
                    continue
                seen_urls.add(hit.url)
                all_hits.append(hit)
            if len(all_hits) >= self.settings.enrichment.max_total_results:
                break

        result.search_hits = len(all_hits)
        logger.info(
            "Enrichment search for '{}' -> {} relevant hits",
            restaurant.name,
            len(all_hits),
        )

        for hit in all_hits:
            kind = classify_url(hit.url)
            source = Source(
                restaurant_id=restaurant.id,
                source_type=f"web_search:{kind}",
                url=hit.url,
                title=hit.title,
                raw_payload={"snippet": hit.snippet, "query": queries[0] if queries else ""},
            )
            result.sources.append(source)

            if kind == "website" and not restaurant.website:
                restaurant.website = hit.url
                result.found_website = True
            elif kind == "facebook" and not restaurant.facebook:
                restaurant.facebook = hit.url
                result.found_social = True
            elif kind == "instagram" and not restaurant.instagram:
                restaurant.instagram = hit.url
                result.found_social = True
            elif kind == "delivery":
                platform = self._delivery_platform_name(hit.url)
                if platform and platform not in restaurant.delivery_platforms:
                    restaurant.delivery_platforms.append(platform)
                    result.found_delivery = True

            # Pull phones/emails from search snippets
            self._apply_snippet_contacts(restaurant, hit.snippet)

        # Deep-fetch official website (or best candidate) for contact details
        candidate = restaurant.website
        if candidate and self.settings.enrichment.fetch_discovered_pages:
            await self._enrich_from_page(restaurant, candidate, result)

        # If still no website, try fetching Facebook/Instagram public pages lightly
        # for phones in og tags / visible text (best effort)
        if self.settings.enrichment.fetch_discovered_pages:
            for url in (restaurant.facebook, restaurant.instagram):
                if url and (not restaurant.phone or not restaurant.email):
                    await self._enrich_from_page(restaurant, url, result)

        # Always keep a Google Maps URL for discoverability
        restaurant.ensure_maps_url()
        if not restaurant.google_maps_url:
            q = quote_plus(
                f"{restaurant.name} {restaurant.address or ''} "
                f"{self.settings.city} {self.settings.state}"
            )
            restaurant.google_maps_url = (
                f"https://www.google.com/maps/search/?api=1&query={q}"
            )

        restaurant.extra = {
            **(restaurant.extra or {}),
            "enrichment": {
                "search_hits": result.search_hits,
                "queries": result.queries,
                "found_website": result.found_website,
                "found_social": result.found_social,
                "found_delivery": result.found_delivery,
            },
        }
        restaurant.touch()
        return result

    @staticmethod
    def _reclassify_misplaced_website(restaurant: Restaurant) -> None:
        """Move Instagram/Facebook URLs stored as website into the right fields."""
        if not restaurant.website:
            return
        kind = classify_url(restaurant.website)
        if kind == "instagram":
            if not restaurant.instagram:
                restaurant.instagram = restaurant.website
            restaurant.website = None
        elif kind == "facebook":
            if not restaurant.facebook:
                restaurant.facebook = restaurant.website
            restaurant.website = None
        elif kind == "delivery":
            platform = None
            for name, pattern in DELIVERY_HOSTS.items():
                if pattern.search(restaurant.website or ""):
                    platform = name
                    break
            if platform and platform not in restaurant.delivery_platforms:
                restaurant.delivery_platforms.append(platform)
            restaurant.website = None

    def _build_queries(self, restaurant: Restaurant) -> list[str]:
        name = restaurant.name.strip()
        city = self.settings.city
        state = "PB"
        base = f'"{name}" {city} {state}'
        queries = [
            f"{base} restaurante",
            f"{base} cardapio",
            f"{base} ifood",
            f"{base} instagram",
            f"{base} facebook telefone",
        ]
        if restaurant.address:
            street = restaurant.address.split(",")[0]
            queries.insert(1, f'"{name}" "{street}" {city}')
        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for q in queries:
            key = q.lower()
            if key not in seen:
                seen.add(key)
                unique.append(q)
        return unique[: self.settings.enrichment.max_queries]

    def _result_matches_restaurant(self, restaurant: Restaurant, hit: SearchResult) -> bool:
        name_norm = normalize_name(restaurant.name)
        blob = normalize_name(f"{hit.title} {hit.snippet} {hit.url}")
        if not name_norm:
            return False
        # Strong containment
        tokens = [t for t in name_norm.split() if len(t) > 2]
        if tokens and sum(1 for t in tokens if t in blob) >= max(1, len(tokens) // 2):
            return True
        score = fuzz.partial_ratio(name_norm, blob)
        return score >= self.settings.enrichment.name_match_threshold

    async def _enrich_from_page(
        self,
        restaurant: Restaurant,
        url: str,
        result: EnrichmentResult,
    ) -> None:
        html = await self.http.get_text(url, check_robots=True)
        if not html:
            return
        extract = self.extractor.extract(html, url)
        before_phone = restaurant.phone
        before_email = restaurant.email
        self.extractor.apply_to_restaurant(restaurant, extract)
        if not restaurant.website and classify_url(url) == "website":
            restaurant.website = url
            result.found_website = True
        for platform in extract.delivery_platforms:
            if platform not in restaurant.delivery_platforms:
                restaurant.delivery_platforms.append(platform)
                result.found_delivery = True
        if extract.facebook and not restaurant.facebook:
            restaurant.facebook = extract.facebook
            result.found_social = True
        if extract.instagram and not restaurant.instagram:
            restaurant.instagram = extract.instagram
            result.found_social = True
        if restaurant.phone != before_phone or restaurant.email != before_email:
            result.sources.append(
                Source(
                    restaurant_id=restaurant.id,
                    source_type="page_extract",
                    url=url,
                    title=extract.title,
                )
            )

    @staticmethod
    def _apply_snippet_contacts(restaurant: Restaurant, snippet: str) -> None:
        if not snippet:
            return
        if not restaurant.phone:
            match = PHONE_RE.search(snippet)
            if match:
                restaurant.phone = normalize_phone(match.group(0)) or match.group(0)
        if not restaurant.email:
            match = EMAIL_RE.search(snippet)
            if match:
                email = match.group(0).lower()
                if not email.endswith((".png", ".jpg", ".gif")):
                    restaurant.email = email

    @staticmethod
    def _delivery_platform_name(url: str) -> str | None:
        for name, pattern in DELIVERY_HOSTS.items():
            if pattern.search(url):
                return name
        return None

    def build_advertising_profile(self, restaurant: Restaurant) -> dict[str, Any]:
        """Compact essential public profile used in exports/reports."""
        return {
            "id": restaurant.id,
            "name": restaurant.name,
            "address": restaurant.address,
            "latitude": restaurant.latitude,
            "longitude": restaurant.longitude,
            "google_maps_url": restaurant.google_maps_url,
            "website": restaurant.website,
            "phone": restaurant.phone,
            "email": restaurant.email,
            "facebook": restaurant.facebook,
            "instagram": restaurant.instagram,
            "delivery_platforms": restaurant.delivery_platforms,
            "categories": restaurant.categories,
            "opening_hours_raw": restaurant.opening_hours_raw,
            "sources": [
                urlparse(u).netloc
                for u in (
                    restaurant.website,
                    restaurant.facebook,
                    restaurant.instagram,
                )
                if u
            ],
        }
