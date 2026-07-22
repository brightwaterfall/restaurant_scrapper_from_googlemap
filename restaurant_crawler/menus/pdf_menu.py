"""Extract menu items from PDF files using pdfplumber / PyMuPDF."""

from __future__ import annotations

import io
import re
from pathlib import Path

from restaurant_crawler.menus.html_menu import RawMenuItem
from restaurant_crawler.menus.price import parse_price
from restaurant_crawler.utils.logging import get_logger

logger = get_logger()


class PdfMenuExtractor:
    def extract_from_path(self, path: str | Path) -> list[RawMenuItem]:
        path = Path(path)
        text = self._read_text(path)
        return self._parse_text(text)

    def extract_from_bytes(self, data: bytes) -> list[RawMenuItem]:
        text = self._read_bytes(data)
        return self._parse_text(text)

    def _read_text(self, path: Path) -> str:
        try:
            import pdfplumber

            chunks: list[str] = []
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    chunks.append(page.extract_text() or "")
            text = "\n".join(chunks).strip()
            if text:
                return text
        except Exception as exc:
            logger.warning("pdfplumber failed for {}: {}", path, exc)

        try:
            import fitz  # PyMuPDF

            doc = fitz.open(path)
            chunks = [page.get_text() for page in doc]
            doc.close()
            return "\n".join(chunks)
        except Exception as exc:
            logger.error("PyMuPDF failed for {}: {}", path, exc)
            return ""

    def _read_bytes(self, data: bytes) -> str:
        try:
            import pdfplumber

            chunks: list[str] = []
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                for page in pdf.pages:
                    chunks.append(page.extract_text() or "")
            text = "\n".join(chunks).strip()
            if text:
                return text
        except Exception as exc:
            logger.warning("pdfplumber bytes failed: {}", exc)

        try:
            import fitz

            doc = fitz.open(stream=data, filetype="pdf")
            chunks = [page.get_text() for page in doc]
            doc.close()
            return "\n".join(chunks)
        except Exception as exc:
            logger.error("PyMuPDF bytes failed: {}", exc)
            return ""

    def _parse_text(self, text: str) -> list[RawMenuItem]:
        if not text:
            return []
        items: list[RawMenuItem] = []
        current_category: str | None = None
        for line in text.splitlines():
            line = re.sub(r"\s+", " ", line).strip()
            if not line:
                continue
            price, currency = parse_price(line)
            if price is None:
                if len(line) < 50 and not re.search(r"\d", line):
                    current_category = line
                continue
            name = re.sub(r"R\$\s*\d.*$", "", line).strip(" .-–")
            name = re.sub(r"\d+[.,]\d{2}\s*$", "", name).strip(" .-–")
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
        return items
