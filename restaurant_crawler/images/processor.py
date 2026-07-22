"""Image validation and metadata extraction with Pillow."""

from __future__ import annotations

from pathlib import Path

from restaurant_crawler.utils.logging import get_logger

logger = get_logger()


def inspect_image(path: Path) -> tuple[int | None, int | None, str | None]:
    try:
        from PIL import Image

        with Image.open(path) as img:
            width, height = img.size
            content_type = Image.MIME.get(img.format or "", None)
            return width, height, content_type
    except Exception as exc:
        logger.debug("Image inspect failed for {}: {}", path, exc)
        return None, None, None


def is_valid_image(path: Path, min_width: int = 200, min_height: int = 200) -> bool:
    width, height, _ = inspect_image(path)
    if width is None or height is None:
        return False
    return width >= min_width and height >= min_height


def slugify_restaurant_name(name: str) -> str:
    from slugify import slugify

    return slugify(name, lowercase=True, max_length=60) or "restaurant"
