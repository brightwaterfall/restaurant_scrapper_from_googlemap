"""Aggregate extractor for restaurant website pages."""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from restaurant_crawler.extractors.contact import (
    extract_address_candidates,
    extract_emails,
    extract_phones,
)
from restaurant_crawler.extractors.hours import extract_opening_hours
from restaurant_crawler.extractors.images import extract_image_urls
from restaurant_crawler.extractors.social import extract_delivery_platforms, extract_social_links
from restaurant_crawler.models.restaurant import OpeningHours, Restaurant


@dataclass
class WebsiteExtract:
    phones: list[str] = field(default_factory=list)
    emails: list[str] = field(default_factory=list)
    addresses: list[str] = field(default_factory=list)
    facebook: str | None = None
    instagram: str | None = None
    whatsapp: str | None = None
    delivery_platforms: list[str] = field(default_factory=list)
    opening_hours: list[OpeningHours] = field(default_factory=list)
    opening_hours_raw: str | None = None
    image_urls: list[str] = field(default_factory=list)
    menu_links: list[str] = field(default_factory=list)
    pdf_links: list[str] = field(default_factory=list)
    title: str | None = None


class WebsiteExtractor:
    MENU_HINTS = ("cardapio", "cardápio", "menu", "carta")
    PDF_HINTS = (".pdf",)

    def extract(self, html: str, base_url: str) -> WebsiteExtract:
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text(" ", strip=True)
        result = WebsiteExtract()
        result.title = (soup.title.string.strip() if soup.title and soup.title.string else None)
        result.phones = extract_phones(soup, text)
        result.emails = extract_emails(soup, text)
        result.addresses = extract_address_candidates(soup)
        social = extract_social_links(soup, base_url)
        result.facebook = social.get("facebook")
        result.instagram = social.get("instagram")
        result.whatsapp = social.get("whatsapp")
        result.delivery_platforms = extract_delivery_platforms(soup, base_url)
        hours, raw = extract_opening_hours(soup)
        result.opening_hours = hours
        result.opening_hours_raw = raw
        result.image_urls = extract_image_urls(soup, base_url)

        for anchor in soup.find_all("a", href=True):
            href = urljoin(base_url, anchor["href"])
            label = (anchor.get_text(" ", strip=True) or "").lower()
            href_l = href.lower()
            if any(h in href_l or h in label for h in self.MENU_HINTS):
                if href not in result.menu_links:
                    result.menu_links.append(href)
            if any(h in href_l for h in self.PDF_HINTS):
                if href not in result.pdf_links:
                    result.pdf_links.append(href)
        return result

    def apply_to_restaurant(self, restaurant: Restaurant, extract: WebsiteExtract) -> Restaurant:
        if not restaurant.phone and extract.phones:
            restaurant.phone = extract.phones[0]
        if not restaurant.email and extract.emails:
            restaurant.email = extract.emails[0]
        if not restaurant.address and extract.addresses:
            restaurant.address = extract.addresses[0]
        if not restaurant.facebook and extract.facebook:
            restaurant.facebook = extract.facebook
        if not restaurant.instagram and extract.instagram:
            restaurant.instagram = extract.instagram
        for platform in extract.delivery_platforms:
            if platform not in restaurant.delivery_platforms:
                restaurant.delivery_platforms.append(platform)
        if extract.opening_hours and not restaurant.opening_hours:
            restaurant.opening_hours = extract.opening_hours
        if extract.opening_hours_raw and not restaurant.opening_hours_raw:
            restaurant.opening_hours_raw = extract.opening_hours_raw
        restaurant.ensure_maps_url()
        restaurant.touch()
        return restaurant
