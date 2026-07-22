"""Contact information extraction (phone, email, address)."""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
)
PHONE_RE = re.compile(
    r"(?:\+?55\s*)?(?:\(?\d{2}\)?\s*)?(?:9?\d{4})[-\s]?\d{4}",
)
TEL_HREF = re.compile(r"^tel:", re.I)
MAILTO_HREF = re.compile(r"^mailto:", re.I)


def extract_emails(soup: BeautifulSoup, text: str) -> list[str]:
    found: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        if MAILTO_HREF.match(href):
            email = href.split(":", 1)[1].split("?")[0].strip()
            if EMAIL_RE.fullmatch(email):
                found.add(email.lower())
    for match in EMAIL_RE.findall(text):
        if not match.lower().endswith((".png", ".jpg", ".gif", ".webp")):
            found.add(match.lower())
    return sorted(found)


def extract_phones(soup: BeautifulSoup, text: str) -> list[str]:
    found: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        if TEL_HREF.match(href):
            phone = href.split(":", 1)[1].strip()
            found.add(phone)
    for match in PHONE_RE.findall(text):
        cleaned = re.sub(r"\s+", " ", match).strip()
        digits = re.sub(r"\D", "", cleaned)
        if len(digits) >= 8:
            found.add(cleaned)
    return sorted(found)


def extract_address_candidates(soup: BeautifulSoup) -> list[str]:
    candidates: list[str] = []
    for selector in (
        "address",
        "[itemprop='address']",
        ".address",
        ".endereco",
        ".endereço",
        "#address",
    ):
        for node in soup.select(selector):
            text = node.get_text(" ", strip=True)
            if text and 10 <= len(text) <= 300:
                candidates.append(text)

    for node in soup.find_all(string=re.compile(r"(Rua|Avenida|Av\.|Travessa)", re.I)):
        parent = node.parent
        if parent:
            text = parent.get_text(" ", strip=True)
            if text and 10 <= len(text) <= 300:
                candidates.append(text)
    # unique preserve order
    seen: set[str] = set()
    unique: list[str] = []
    for item in candidates:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def absolutize(base: str, href: str) -> str:
    return urljoin(base, href)
