"""OCR helpers for image-based menus (Tesseract)."""

from __future__ import annotations

from pathlib import Path

from restaurant_crawler.config.settings import Settings
from restaurant_crawler.utils.logging import get_logger

logger = get_logger()


class OcrEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._configured = False

    def _configure(self) -> bool:
        if self._configured:
            return True
        if not self.settings.ocr.enabled:
            return False
        try:
            import pytesseract
            from PIL import Image  # noqa: F401
        except ImportError:
            logger.warning("OCR dependencies missing (pytesseract/Pillow)")
            return False

        if self.settings.ocr.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = self.settings.ocr.tesseract_cmd
        self._configured = True
        return True

    def image_to_text(self, path: str | Path) -> str:
        if not self._configure():
            return ""
        try:
            import pytesseract
            from PIL import Image

            image = Image.open(path)
            # Convert / enhance slightly for OCR
            if image.mode not in {"RGB", "L"}:
                image = image.convert("RGB")
            text = pytesseract.image_to_string(image, lang=self.settings.ocr.language)
            return text or ""
        except Exception as exc:
            logger.warning("OCR failed for {}: {}", path, exc)
            return ""
