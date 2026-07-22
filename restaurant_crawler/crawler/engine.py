"""Main crawl orchestration engine."""

from __future__ import annotations

import asyncio
import time
from typing import Any
from urllib.parse import urljoin, urlparse

from restaurant_crawler.config.settings import Settings, get_settings
from restaurant_crawler.crawler.browser import BrowserFetcher
from restaurant_crawler.crawler.discovery import RestaurantDiscovery
from restaurant_crawler.crawler.enrichment import RestaurantEnricher
from restaurant_crawler.crawler.resume import CrawlStateManager
from restaurant_crawler.crawler.web_search import ensure_http_url
from restaurant_crawler.crawler.website_detector import WebsiteDetector, WebsiteType
from restaurant_crawler.database.connection import Database
from restaurant_crawler.database.repository import RestaurantRepository
from restaurant_crawler.extractors.website_extractor import WebsiteExtractor
from restaurant_crawler.images.downloader import ImageDownloader
from restaurant_crawler.menus.parser import MenuParser
from restaurant_crawler.models.restaurant import Restaurant
from restaurant_crawler.models.source import CrawlLog, Source
from restaurant_crawler.utils.deduplication import Deduplicator
from restaurant_crawler.utils.http_client import HttpClient
from restaurant_crawler.utils.logging import get_logger, setup_logging
from restaurant_crawler.utils.normalize import make_fingerprint, normalize_address, normalize_name

logger = get_logger()


class CrawlEngine:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        setup_logging(
            self.settings.logs_path,
            level=self.settings.log_level,
            rotation=self.settings.log_rotation,
            retention=self.settings.log_retention,
        )
        self.settings.ensure_directories()
        self.db = Database(self.settings.db_path)
        self.repo = RestaurantRepository(self.db)
        self.state = CrawlStateManager(self.repo, self.settings.state_path)
        self.detector = WebsiteDetector()
        self.extractor = WebsiteExtractor()
        self.deduper = Deduplicator(threshold=self.settings.dedup_threshold)
        self.deduper.load(self.repo.list_restaurants())

    async def crawl(self, resume: bool = False) -> dict[str, Any]:
        started = time.perf_counter()
        self.state.mark_started()
        stats: dict[str, Any] = {
            "discovered": 0,
            "scraped": 0,
            "failed": 0,
            "menus": 0,
            "photos": 0,
            "enriched": 0,
            "websites_found": 0,
            "resumed": resume,
        }

        async with HttpClient(self.settings) as http:
            discovery = RestaurantDiscovery(self.settings, http)
            browser = BrowserFetcher(self.settings)
            menu_parser = MenuParser(self.settings, http)
            image_dl = ImageDownloader(self.settings, http)

            try:
                if not resume or self.repo.count_restaurants() == 0:
                    pairs = await discovery.discover_overpass()
                    restaurants = [r for r, _ in pairs]
                    await discovery.enrich_with_nominatim(restaurants)
                    for restaurant, source in pairs:
                        saved = self._persist_discovered(restaurant, source)
                        if saved:
                            stats["discovered"] += 1
                else:
                    logger.info("Resume mode: skipping discovery, processing pending restaurants")

                pending = self.repo.list_pending()
                logger.info("Scraping {} restaurants", len(pending))

                semaphore = asyncio.Semaphore(self.settings.max_concurrent)

                async def worker(restaurant: Restaurant) -> None:
                    async with semaphore:
                        try:
                            await self._scrape_restaurant(
                                restaurant, http, browser, menu_parser, image_dl, stats
                            )
                        except Exception as exc:
                            logger.exception("Unhandled scrape error for {}: {}", restaurant.name, exc)
                            restaurant.status = "failed"
                            restaurant.scrape_error = str(exc)
                            self.repo.upsert_restaurant(restaurant)
                            stats["failed"] += 1
                            self.repo.insert_log(
                                CrawlLog(
                                    restaurant_id=restaurant.id,
                                    level="ERROR",
                                    event="scrape_failed",
                                    message=str(exc),
                                    url=restaurant.website,
                                )
                            )

                await asyncio.gather(*[worker(r) for r in pending])
            finally:
                await browser.close()

        elapsed = time.perf_counter() - started
        stats["elapsed_seconds"] = round(elapsed, 2)
        stats.update(self.repo.stats())
        self.state.mark_finished(stats)
        logger.info("Crawl finished in {:.2f}s: {}", elapsed, stats)
        return stats

    def _persist_discovered(self, restaurant: Restaurant, source: Source) -> bool:
        match = self.deduper.find_duplicate(restaurant)
        if match.is_duplicate and match.existing:
            merged = self.deduper.merge(match.existing, restaurant)
            self.repo.upsert_restaurant(merged)
            source.restaurant_id = merged.id
            self.repo.insert_source(source)
            self.repo.insert_log(
                CrawlLog(
                    restaurant_id=merged.id,
                    level="INFO",
                    event="deduplicated",
                    message=f"Merged into existing ({match.reason}, {match.score:.1f})",
                    url=source.url,
                )
            )
            return False

        restaurant.normalized_name = normalize_name(restaurant.name)
        restaurant.normalized_address = normalize_address(restaurant.address)
        restaurant.fingerprint = make_fingerprint(
            restaurant.name,
            restaurant.address,
            restaurant.latitude,
            restaurant.longitude,
            restaurant.website,
            restaurant.phone,
        )
        self.repo.upsert_restaurant(restaurant)
        source.restaurant_id = restaurant.id
        self.repo.insert_source(source)
        self.deduper.register(restaurant)
        self.repo.insert_log(
            CrawlLog(
                restaurant_id=restaurant.id,
                level="INFO",
                event="discovered",
                message=f"Discovered {restaurant.name}",
                url=source.url,
            )
        )
        return True

    async def _scrape_restaurant(
        self,
        restaurant: Restaurant,
        http: HttpClient,
        browser: BrowserFetcher,
        menu_parser: MenuParser,
        image_dl: ImageDownloader,
        stats: dict[str, Any],
    ) -> None:
        logger.info("Scraping: {}", restaurant.name)
        self.repo.insert_log(
            CrawlLog(
                restaurant_id=restaurant.id,
                level="INFO",
                event="scrape_start",
                message=f"Start scrape for {restaurant.name}",
                url=restaurant.website,
            )
        )

        # Normalize bare domains and enrich from public web/social/delivery search
        restaurant.website = ensure_http_url(restaurant.website)
        enricher = RestaurantEnricher(self.settings, http)
        if (
            self.settings.enrichment.enrich_during_crawl
            and enricher.needs_enrichment(restaurant)
        ):
            enrichment = await enricher.enrich(restaurant)
            for source in enrichment.sources:
                self.repo.insert_source(source)
            stats["enriched"] = stats.get("enriched", 0) + 1
            if enrichment.found_website:
                stats["websites_found"] = stats.get("websites_found", 0) + 1
            self.repo.insert_log(
                CrawlLog(
                    restaurant_id=restaurant.id,
                    level="INFO",
                    event="enriched",
                    message=(
                        f"Web enrichment hits={enrichment.search_hits}; "
                        f"website={bool(restaurant.website)}; "
                        f"phone={bool(restaurant.phone)}; "
                        f"social={enrichment.found_social}; "
                        f"delivery={enrichment.found_delivery}"
                    ),
                    url=restaurant.website,
                    details=enricher.build_advertising_profile(restaurant),
                )
            )
            self.repo.upsert_restaurant(restaurant)

        if not restaurant.website:
            # No official site found — keep Maps/social/delivery essentials and continue
            restaurant.status = "scraped"
            restaurant.ensure_maps_url()
            self.repo.upsert_restaurant(restaurant)
            stats["scraped"] += 1
            return

        html = await http.get_text(restaurant.website)
        detection = self.detector.detect(html or "", restaurant.website)
        if detection.website_type == WebsiteType.DYNAMIC or not html:
            html = await browser.fetch_html(
                restaurant.website,
                scroll=detection.has_infinite_scroll or True,
            )
            detection = self.detector.detect(html or "", restaurant.website)

        if not html:
            restaurant.status = "failed"
            restaurant.scrape_error = "failed_to_fetch_website"
            self.repo.upsert_restaurant(restaurant)
            stats["failed"] += 1
            return

        extract = self.extractor.extract(html, restaurant.website)
        self.extractor.apply_to_restaurant(restaurant, extract)

        # Follow pagination lightly (same domain, few pages)
        if detection.has_pagination:
            html = await self._follow_pagination(restaurant.website, html, http, browser)

        # Persist sources
        self.repo.insert_source(
            Source(
                restaurant_id=restaurant.id,
                source_type="website",
                url=restaurant.website,
                title=extract.title,
            )
        )

        # Menus
        menu_urls = list(dict.fromkeys(extract.menu_links + extract.pdf_links))
        if not menu_urls:
            menu_urls = [restaurant.website]
        menus_found = 0
        for menu_url in menu_urls[:5]:
            try:
                page_html = html if menu_url.rstrip("/") == restaurant.website.rstrip("/") else None
                if page_html is None and not menu_url.lower().endswith(
                    (".pdf", ".jpg", ".jpeg", ".png", ".webp")
                ):
                    page_html = await http.get_text(menu_url)
                    if page_html and self.detector.detect(page_html, menu_url).website_type == WebsiteType.DYNAMIC:
                        page_html = await browser.fetch_html(menu_url, scroll=True)
                menu, items = await menu_parser.parse_url(menu_url, restaurant.id, html=page_html)
                if items:
                    self.repo.upsert_menu(menu)
                    self.repo.delete_menu_items_for_menu(menu.id)
                    self.repo.insert_menu_items(items)
                    menus_found += len(items)
                    stats["menus"] += len(items)
            except Exception as exc:
                logger.warning("Menu parse failed for {}: {}", menu_url, exc)

        # Images
        photos = await image_dl.download_for_restaurant(restaurant, extract.image_urls)
        for photo in photos:
            self.repo.upsert_photo(photo)
            if photo.downloaded:
                stats["photos"] += 1

        restaurant.status = "scraped"
        restaurant.scrape_error = None
        restaurant.normalized_name = normalize_name(restaurant.name)
        restaurant.normalized_address = normalize_address(restaurant.address)
        restaurant.fingerprint = make_fingerprint(
            restaurant.name,
            restaurant.address,
            restaurant.latitude,
            restaurant.longitude,
            restaurant.website,
            restaurant.phone,
        )
        restaurant.ensure_maps_url()
        self.repo.upsert_restaurant(restaurant)
        stats["scraped"] += 1
        self.repo.insert_log(
            CrawlLog(
                restaurant_id=restaurant.id,
                level="INFO",
                event="scrape_done",
                message=f"Scraped {restaurant.name}; menus={menus_found}; photos={len(photos)}",
                url=restaurant.website,
                details={"website_type": detection.website_type.value},
            )
        )

    async def _follow_pagination(
        self,
        base_url: str,
        html: str,
        http: HttpClient,
        browser: BrowserFetcher,
        max_pages: int = 3,
    ) -> str:
        from bs4 import BeautifulSoup

        combined = [html]
        current_html = html
        base_host = urlparse(base_url).netloc
        for _ in range(max_pages - 1):
            soup = BeautifulSoup(current_html, "lxml")
            next_link = soup.select_one("a[rel='next'], .pagination a.next, .pager a.next")
            if not next_link or not next_link.get("href"):
                break
            next_url = urljoin(base_url, next_link["href"])
            if urlparse(next_url).netloc != base_host:
                break
            page = await http.get_text(next_url)
            if not page:
                page = await browser.fetch_html(next_url)
            if not page:
                break
            combined.append(page)
            current_html = page
        return "\n".join(combined)

    async def enrich_incomplete(self, limit: int | None = None) -> dict[str, Any]:
        """Search the public web for restaurants missing website/phone/social data."""
        targets = self.repo.list_incomplete_profiles()
        if limit is not None:
            targets = targets[:limit]
        stats: dict[str, Any] = {
            "candidates": len(targets),
            "enriched": 0,
            "websites_found": 0,
            "phones_found": 0,
            "social_found": 0,
            "delivery_found": 0,
        }
        logger.info("Enriching {} incomplete restaurant profiles", len(targets))

        async with HttpClient(self.settings) as http:
            enricher = RestaurantEnricher(self.settings, http)
            semaphore = asyncio.Semaphore(self.settings.max_concurrent)

            async def worker(restaurant: Restaurant) -> None:
                async with semaphore:
                    had_website = bool(restaurant.website)
                    had_phone = bool(restaurant.phone)
                    try:
                        enrichment = await enricher.enrich(restaurant)
                        for source in enrichment.sources:
                            self.repo.insert_source(source)
                        self.repo.upsert_restaurant(restaurant)
                        stats["enriched"] += 1
                        if restaurant.website and not had_website:
                            stats["websites_found"] += 1
                        if restaurant.phone and not had_phone:
                            stats["phones_found"] += 1
                        if enrichment.found_social:
                            stats["social_found"] += 1
                        if enrichment.found_delivery:
                            stats["delivery_found"] += 1
                        self.repo.insert_log(
                            CrawlLog(
                                restaurant_id=restaurant.id,
                                level="INFO",
                                event="enriched",
                                message=(
                                    f"Enriched {restaurant.name}: "
                                    f"hits={enrichment.search_hits} "
                                    f"website={restaurant.website} "
                                    f"phone={restaurant.phone}"
                                ),
                                url=restaurant.website,
                                details=enricher.build_advertising_profile(restaurant),
                            )
                        )
                        # If a website was newly found, scrape it for menu/photos
                        if restaurant.website and not had_website:
                            restaurant.status = "discovered"
                            self.repo.upsert_restaurant(restaurant)
                    except Exception as exc:
                        logger.error("Enrichment failed for {}: {}", restaurant.name, exc)

            await asyncio.gather(*[worker(r) for r in targets])

        # Scrape restaurants that gained a website during enrichment
        pending = [r for r in self.repo.list_pending() if r.website]
        if pending:
            logger.info("Scraping {} restaurants with newly found websites", len(pending))
            async with HttpClient(self.settings) as http:
                browser = BrowserFetcher(self.settings)
                menu_parser = MenuParser(self.settings, http)
                image_dl = ImageDownloader(self.settings, http)
                scrape_stats: dict[str, Any] = {
                    "scraped": 0,
                    "failed": 0,
                    "menus": 0,
                    "photos": 0,
                }
                try:
                    semaphore = asyncio.Semaphore(self.settings.max_concurrent)

                    async def scrape_worker(restaurant: Restaurant) -> None:
                        async with semaphore:
                            await self._scrape_restaurant(
                                restaurant,
                                http,
                                browser,
                                menu_parser,
                                image_dl,
                                scrape_stats,
                            )

                    await asyncio.gather(*[scrape_worker(r) for r in pending])
                finally:
                    await browser.close()
            stats["followup_scrape"] = scrape_stats

        return stats

    async def process_menus_only(self) -> dict[str, Any]:
        async with HttpClient(self.settings) as http:
            browser = BrowserFetcher(self.settings)
            menu_parser = MenuParser(self.settings, http)
            count = 0
            try:
                for restaurant in self.repo.list_restaurants():
                    if not restaurant.website:
                        continue
                    html = await http.get_text(restaurant.website) or ""
                    if self.detector.detect(html, restaurant.website).website_type == WebsiteType.DYNAMIC:
                        html = await browser.fetch_html(restaurant.website, scroll=True) or ""
                    extract = self.extractor.extract(html, restaurant.website)
                    urls = extract.menu_links + extract.pdf_links
                    if not urls:
                        urls = [restaurant.website]
                    for url in urls[:5]:
                        menu, items = await menu_parser.parse_url(
                            url,
                            restaurant.id,
                            html=html if url == restaurant.website else None,
                        )
                        if items:
                            self.repo.upsert_menu(menu)
                            self.repo.delete_menu_items_for_menu(menu.id)
                            self.repo.insert_menu_items(items)
                            count += len(items)
            finally:
                await browser.close()
        return {"menu_items": count}

    async def process_images_only(self) -> dict[str, Any]:
        async with HttpClient(self.settings) as http:
            browser = BrowserFetcher(self.settings)
            image_dl = ImageDownloader(self.settings, http)
            downloaded = 0
            try:
                restaurants = {r.id: r for r in self.repo.list_restaurants()}
                # Re-scan websites for image URLs when none pending
                pending = self.repo.list_undownloaded_photos()
                if not pending:
                    for restaurant in restaurants.values():
                        if not restaurant.website:
                            continue
                        html = await http.get_text(restaurant.website) or ""
                        if not html:
                            html = await browser.fetch_html(restaurant.website) or ""
                        extract = self.extractor.extract(html, restaurant.website)
                        photos = await image_dl.download_for_restaurant(
                            restaurant, extract.image_urls
                        )
                        for photo in photos:
                            self.repo.upsert_photo(photo)
                            if photo.downloaded:
                                downloaded += 1
                else:
                    updated = await image_dl.download_pending(pending, restaurants)
                    for photo in updated:
                        self.repo.upsert_photo(photo)
                        if photo.downloaded:
                            downloaded += 1
            finally:
                await browser.close()
        return {"photos_downloaded": downloaded}
