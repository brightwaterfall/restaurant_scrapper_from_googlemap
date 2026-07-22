"""Extract menu items from HTML pages."""

from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup, Tag

from restaurant_crawler.menus.price import parse_price


@dataclass
class RawMenuItem:
    category: str | None
    name: str
    description: str | None
    price: float | None
    currency: str
    notes: str | None = None
    availability: str | None = None


class HtmlMenuExtractor:
    ITEM_SELECTORS = (
        ".menu-item",
        ".cardapio-item",
        ".product",
        ".dish",
        "li.item",
        "[itemtype*='MenuItem']",
        ".woocommerce-LoopProduct-link",
    )

    CATEGORY_SELECTORS = (
        "h2",
        "h3",
        ".menu-category",
        ".category-title",
        ".cardapio-categoria",
    )

    def extract(self, html: str) -> list[RawMenuItem]:
        soup = BeautifulSoup(html, "lxml")
        items = self._extract_structured(soup)
        if items:
            return items
        return self._extract_heuristic(soup)

    def _extract_structured(self, soup: BeautifulSoup) -> list[RawMenuItem]:
        items: list[RawMenuItem] = []
        current_category: str | None = None

        # Walk common containers
        for node in soup.find_all(["h2", "h3", "div", "li", "article", "section"]):
            if not isinstance(node, Tag):
                continue
            classes = " ".join(node.get("class", [])).lower()
            if node.name in {"h2", "h3"} or "categor" in classes:
                text = node.get_text(" ", strip=True)
                if text and len(text) < 80:
                    current_category = text
                continue

            if not any(sel.lstrip(".") in classes for sel in (".menu-item", ".product", ".dish", ".cardapio-item")):
                if node.get("itemtype") and "MenuItem" not in str(node.get("itemtype")):
                    continue
                if "menu-item" not in classes and "product" not in classes and "dish" not in classes:
                    continue

            name_node = (
                node.select_one(".name, .product-title, .item-name, h4, h3, [itemprop='name']")
                or node.find(["h3", "h4", "strong"])
            )
            price_node = node.select_one(".price, .valor, [itemprop='price']")
            desc_node = node.select_one(".description, .desc, [itemprop='description'], p")

            name = name_node.get_text(" ", strip=True) if name_node else node.get_text(" ", strip=True)
            if not name or len(name) < 2 or len(name) > 120:
                continue
            price_text = price_node.get_text(" ", strip=True) if price_node else ""
            if not price_text:
                price_text = node.get_text(" ", strip=True)
            price, currency = parse_price(price_text)
            description = desc_node.get_text(" ", strip=True) if desc_node else None
            if description and description == name:
                description = None
            items.append(
                RawMenuItem(
                    category=current_category,
                    name=name,
                    description=description,
                    price=price,
                    currency=currency,
                )
            )
        return self._dedupe(items)

    def _extract_heuristic(self, soup: BeautifulSoup) -> list[RawMenuItem]:
        items: list[RawMenuItem] = []
        current_category: str | None = None
        for node in soup.find_all(["h2", "h3", "p", "li", "div", "tr"]):
            text = node.get_text(" ", strip=True)
            if not text or len(text) > 250:
                continue
            if node.name in {"h2", "h3"} and len(text) < 60:
                current_category = text
                continue
            price, currency = parse_price(text)
            if price is None:
                continue
            # Remove price from name
            name = re.sub(r"R\$\s*\d.*$", "", text).strip(" -–|:")
            name = re.sub(r"\d+[.,]\d{2}\s*$", "", name).strip(" -–|:")
            if len(name) < 2:
                continue
            items.append(
                RawMenuItem(
                    category=current_category,
                    name=name[:120],
                    description=None,
                    price=price,
                    currency=currency,
                )
            )
        return self._dedupe(items)

    @staticmethod
    def _dedupe(items: list[RawMenuItem]) -> list[RawMenuItem]:
        seen: set[str] = set()
        unique: list[RawMenuItem] = []
        for item in items:
            key = f"{item.category}|{item.name.lower()}|{item.price}"
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
        return unique
