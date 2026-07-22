"""Optional Scrapy spider for directory-style HTML discovery.

The primary discovery path uses the Overpass API (async). This spider is
provided for sites that expose public restaurant listings as paginated HTML.
"""

from __future__ import annotations

from urllib.parse import urljoin

import scrapy
from bs4 import BeautifulSoup


class DirectoryListingSpider(scrapy.Spider):
    name = "directory_listing"
    custom_settings = {
        "ROBOTSTXT_OBEY": True,
        "DOWNLOAD_DELAY": 1.5,
        "CONCURRENT_REQUESTS": 4,
        "USER_AGENT": "RestaurantCrawler/1.0 (+research; polite bot)",
        "LOG_LEVEL": "INFO",
    }

    def __init__(
        self,
        start_url: str | None = None,
        item_selector: str = "a.restaurant, .listing a, .place-card a",
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.start_urls = [start_url] if start_url else []
        self.item_selector = item_selector

    def parse(self, response):
        soup = BeautifulSoup(response.text, "lxml")
        for node in soup.select(self.item_selector):
            href = node.get("href")
            name = node.get_text(" ", strip=True)
            if not href or not name:
                continue
            yield {
                "name": name,
                "url": urljoin(response.url, href),
                "source_url": response.url,
            }

        next_link = soup.select_one("a[rel='next'], .pagination a.next")
        if next_link and next_link.get("href"):
            yield response.follow(next_link["href"], callback=self.parse)
