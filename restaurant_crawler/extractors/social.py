"""Social network and delivery platform link extraction."""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

SOCIAL_PATTERNS = {
    "facebook": re.compile(r"facebook\.com/|fb\.com/", re.I),
    "instagram": re.compile(r"instagram\.com/", re.I),
    "whatsapp": re.compile(r"wa\.me/|api\.whatsapp\.com|whatsapp\.com", re.I),
}

DELIVERY_PATTERNS = {
    "iFood": re.compile(r"ifood\.com\.br", re.I),
    "Rappi": re.compile(r"rappi\.com", re.I),
    "Uber Eats": re.compile(r"ubereats\.com|uber\.com/.*eats", re.I),
    "99Food": re.compile(r"99app\.com|99food", re.I),
    "Aiqfome": re.compile(r"aiqfome\.com", re.I),
    "Delivery Much": re.compile(r"deliverymuch\.com\.br", re.I),
}


def extract_social_links(soup: BeautifulSoup, base_url: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for anchor in soup.find_all("a", href=True):
        href = urljoin(base_url, anchor["href"])
        for key, pattern in SOCIAL_PATTERNS.items():
            if pattern.search(href) and key not in result:
                result[key] = href
    return result


def extract_delivery_platforms(soup: BeautifulSoup, base_url: str) -> list[str]:
    found: list[str] = []
    for anchor in soup.find_all("a", href=True):
        href = urljoin(base_url, anchor["href"])
        for name, pattern in DELIVERY_PATTERNS.items():
            if pattern.search(href) and name not in found:
                found.append(name)
    text = soup.get_text(" ", strip=True).lower()
    for name, pattern in DELIVERY_PATTERNS.items():
        if name not in found and pattern.search(text):
            found.append(name)
    return found


def is_same_domain(url: str, base: str) -> bool:
    return urlparse(url).netloc == urlparse(base).netloc
