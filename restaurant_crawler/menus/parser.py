"""Unified menu parser orchestrating HTML / PDF / image extractors."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from restaurant_crawler.config.settings import Settings
from restaurant_crawler.menus.html_menu import HtmlMenuExtractor, RawMenuItem
from restaurant_crawler.menus.image_menu import ImageMenuExtractor
from restaurant_crawler.menus.ocr import OcrEngine
from restaurant_crawler.menus.pdf_menu import PdfMenuExtractor
from restaurant_crawler.models.menu import Menu, MenuItem
from restaurant_crawler.utils.http_client import HttpClient
from restaurant_crawler.utils.logging import get_logger

logger = get_logger()


class MenuParser:
    def __init__(self, settings: Settings, http: HttpClient) -> None:
        self.settings = settings
        self.http = http
        self.html_extractor = HtmlMenuExtractor()
        self.pdf_extractor = PdfMenuExtractor()
        self.ocr = OcrEngine(settings)
        self.image_extractor = ImageMenuExtractor(self.ocr)
        self.menus_dir = settings.menus_path
        self.menus_dir.mkdir(parents=True, exist_ok=True)

    async def parse_html(self, html: str, restaurant_id: str, source_url: str) -> tuple[Menu, list[MenuItem]]:
        raw_items = self.html_extractor.extract(html)
        return self._to_models(raw_items, restaurant_id, source_url, "html")

    async def parse_url(self, url: str, restaurant_id: str, html: str | None = None) -> tuple[Menu, list[MenuItem]]:
        path = urlparse(url).path.lower()
        if path.endswith(".pdf"):
            return await self.parse_pdf_url(url, restaurant_id)
        if path.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")):
            return await self.parse_image_url(url, restaurant_id)
        if html is None:
            html = await self.http.get_text(url) or ""
        return await self.parse_html(html, restaurant_id, url)

    async def parse_pdf_url(self, url: str, restaurant_id: str) -> tuple[Menu, list[MenuItem]]:
        data = await self.http.get_bytes(url)
        local_path = None
        raw_items: list[RawMenuItem] = []
        if data:
            local_path = self.menus_dir / f"{restaurant_id}_menu.pdf"
            local_path.write_bytes(data)
            raw_items = self.pdf_extractor.extract_from_bytes(data)
        menu, items = self._to_models(raw_items, restaurant_id, url, "pdf")
        if local_path:
            menu.local_path = str(local_path)
        return menu, items

    async def parse_image_url(self, url: str, restaurant_id: str) -> tuple[Menu, list[MenuItem]]:
        data = await self.http.get_bytes(url)
        local_path = None
        raw_items: list[RawMenuItem] = []
        if data:
            ext = Path(urlparse(url).path).suffix or ".jpg"
            local_path = self.menus_dir / f"{restaurant_id}_menu{ext}"
            local_path.write_bytes(data)
            raw_items = self.image_extractor.extract_from_path(local_path)
        menu, items = self._to_models(raw_items, restaurant_id, url, "ocr" if raw_items else "image")
        if local_path:
            menu.local_path = str(local_path)
        return menu, items

    def parse_local_file(self, path: Path, restaurant_id: str) -> tuple[Menu, list[MenuItem]]:
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            raw = self.pdf_extractor.extract_from_path(path)
            source_type = "pdf"
        elif suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".tif", ".tiff", ".bmp"}:
            raw = self.image_extractor.extract_from_path(path)
            source_type = "ocr"
        else:
            html = path.read_text(encoding="utf-8", errors="ignore")
            raw = self.html_extractor.extract(html)
            source_type = "html"
        menu, items = self._to_models(raw, restaurant_id, str(path), source_type)
        menu.local_path = str(path)
        return menu, items

    def _to_models(
        self,
        raw_items: list[RawMenuItem],
        restaurant_id: str,
        source_url: str,
        source_type: str,
    ) -> tuple[Menu, list[MenuItem]]:
        menu = Menu(
            restaurant_id=restaurant_id,
            title="Menu",
            source_url=source_url,
            source_type=source_type,
            currency="BRL",
            item_count=len(raw_items),
            extracted=bool(raw_items),
        )
        items = [
            MenuItem(
                menu_id=menu.id,
                restaurant_id=restaurant_id,
                category=raw.category,
                name=raw.name,
                description=raw.description,
                price=raw.price,
                currency=raw.currency or "BRL",
                notes=raw.notes,
                availability=raw.availability,
                source_type=source_type,
            )
            for raw in raw_items
        ]
        logger.info(
            "Parsed {} menu items ({}) for restaurant {}",
            len(items),
            source_type,
            restaurant_id,
        )
        return menu, items
