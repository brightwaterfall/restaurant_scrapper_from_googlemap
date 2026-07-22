"""Extract menu items from menu images via OCR."""

from __future__ import annotations

from pathlib import Path

from restaurant_crawler.menus.html_menu import RawMenuItem
from restaurant_crawler.menus.ocr import OcrEngine
from restaurant_crawler.menus.pdf_menu import PdfMenuExtractor


class ImageMenuExtractor:
    def __init__(self, ocr: OcrEngine) -> None:
        self.ocr = ocr
        self._text_parser = PdfMenuExtractor()

    def extract_from_path(self, path: str | Path) -> list[RawMenuItem]:
        text = self.ocr.image_to_text(path)
        if not text.strip():
            return []
        return self._text_parser._parse_text(text)
