"""Concurrent high-resolution image downloader."""

from __future__ import annotations

import asyncio
from pathlib import Path

from restaurant_crawler.config.settings import Settings
from restaurant_crawler.extractors.images import is_likely_thumbnail
from restaurant_crawler.images.processor import inspect_image, is_valid_image, slugify_restaurant_name
from restaurant_crawler.models.photo import Photo
from restaurant_crawler.models.restaurant import Restaurant
from restaurant_crawler.utils.http_client import HttpClient
from restaurant_crawler.utils.logging import get_logger

logger = get_logger()


class ImageDownloader:
    def __init__(self, settings: Settings, http: HttpClient) -> None:
        self.settings = settings
        self.http = http
        self.images_dir = settings.images_path
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self._semaphore = asyncio.Semaphore(settings.images.concurrent_downloads)

    def restaurant_dir(self, restaurant: Restaurant) -> Path:
        folder = self.images_dir / slugify_restaurant_name(restaurant.name)
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    async def download_for_restaurant(
        self,
        restaurant: Restaurant,
        urls: list[str],
        existing_count: int = 0,
    ) -> list[Photo]:
        max_count = self.settings.images.max_per_restaurant
        selected = urls[: max(0, max_count - existing_count)]
        photos: list[Photo] = []
        index = existing_count + 1
        tasks = [
            self._download_one(restaurant, url, index + offset)
            for offset, url in enumerate(selected)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Photo):
                photos.append(result)
            elif isinstance(result, Exception):
                logger.error("Image download error: {}", result)
        return photos

    async def _download_one(self, restaurant: Restaurant, url: str, index: int) -> Photo:
        async with self._semaphore:
            slug = slugify_restaurant_name(restaurant.name)
            filename = f"{slug}_{index:03d}.jpg"
            dest_dir = self.restaurant_dir(restaurant)
            dest = dest_dir / filename
            photo = Photo(
                restaurant_id=restaurant.id,
                source_url=url,
                filename=filename,
                is_thumbnail=is_likely_thumbnail(url),
            )
            if photo.is_thumbnail and self.settings.images.prefer_original:
                # still try; may upgrade later
                pass

            data = await self.http.get_bytes(url)
            if not data:
                photo.download_error = "empty_response"
                return photo

            # Detect extension from content / URL
            ext = ".jpg"
            lower = url.lower()
            for candidate in (".png", ".webp", ".gif", ".jpeg", ".jpg"):
                if candidate in lower:
                    ext = ".jpg" if candidate == ".jpeg" else candidate
                    break
            filename = f"{slug}_{index:03d}{ext}"
            dest = dest_dir / filename
            dest.write_bytes(data)

            width, height, content_type = inspect_image(dest)
            photo.filename = filename
            photo.local_path = str(dest)
            photo.width = width
            photo.height = height
            photo.content_type = content_type
            photo.file_size = dest.stat().st_size
            photo.is_thumbnail = is_likely_thumbnail(url, width, height)

            if not is_valid_image(
                dest,
                self.settings.images.min_width,
                self.settings.images.min_height,
            ):
                photo.downloaded = False
                photo.download_error = "below_min_resolution"
                try:
                    dest.unlink(missing_ok=True)
                except Exception:
                    pass
                photo.local_path = None
                return photo

            photo.downloaded = True
            logger.debug("Downloaded image {} -> {}", url, dest)
            return photo

    async def download_pending(self, photos: list[Photo], restaurants: dict[str, Restaurant]) -> list[Photo]:
        updated: list[Photo] = []
        # Group by restaurant for naming continuity
        by_rest: dict[str, list[Photo]] = {}
        for photo in photos:
            by_rest.setdefault(photo.restaurant_id, []).append(photo)

        for restaurant_id, group in by_rest.items():
            restaurant = restaurants.get(restaurant_id)
            if not restaurant:
                continue
            existing = len(
                [
                    p
                    for p in group
                    if p.downloaded
                ]
            )
            # Re-download only those without local files
            pending = [p for p in group if not p.downloaded]
            urls = [p.source_url for p in pending]
            new_photos = await self.download_for_restaurant(restaurant, urls, existing_count=existing)
            updated.extend(new_photos)
        return updated
