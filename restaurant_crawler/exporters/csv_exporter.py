"""Export SQLite tables to UTF-8 CSV files via Pandas."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from restaurant_crawler.config.settings import Settings
from restaurant_crawler.database.repository import RestaurantRepository
from restaurant_crawler.utils.logging import get_logger

logger = get_logger()


class CsvExporter:
    FILES = (
        "restaurants.csv",
        "menus.csv",
        "menu_items.csv",
        "photos.csv",
        "sources.csv",
    )

    def __init__(self, settings: Settings, repo: RestaurantRepository) -> None:
        self.settings = settings
        self.repo = repo
        self.output = settings.output_path
        self.output.mkdir(parents=True, exist_ok=True)

    def export_all(self) -> dict[str, str]:
        paths: dict[str, str] = {}
        paths["restaurants.csv"] = str(self._export_restaurants())
        paths["menus.csv"] = str(self._export_menus())
        paths["menu_items.csv"] = str(self._export_menu_items())
        paths["photos.csv"] = str(self._export_photos())
        paths["sources.csv"] = str(self._export_sources())
        logger.info("CSV export complete -> {}", self.output)
        return paths

    def _write(self, name: str, rows: list[dict]) -> Path:
        path = self.output / name
        df = pd.DataFrame(rows)
        df.to_csv(path, index=False, encoding="utf-8")
        return path

    def _export_restaurants(self) -> Path:
        rows = []
        for r in self.repo.list_restaurants():
            rows.append(
                {
                    "id": r.id,
                    "name": r.name,
                    "address": r.address,
                    "city": r.city,
                    "state": r.state,
                    "country": r.country,
                    "latitude": r.latitude,
                    "longitude": r.longitude,
                    "google_maps_url": r.google_maps_url,
                    "website": r.website,
                    "phone": r.phone,
                    "email": r.email,
                    "facebook": r.facebook,
                    "instagram": r.instagram,
                    "delivery_platforms": "|".join(r.delivery_platforms),
                    "categories": "|".join(r.categories),
                    "opening_hours_raw": r.opening_hours_raw,
                    "currency": r.currency,
                    "status": r.status,
                    "created_at": r.created_at.isoformat(),
                    "updated_at": r.updated_at.isoformat(),
                }
            )
        return self._write("restaurants.csv", rows)

    def _export_menus(self) -> Path:
        rows = [
            {
                "id": m.id,
                "restaurant_id": m.restaurant_id,
                "title": m.title,
                "source_url": m.source_url,
                "source_type": m.source_type,
                "local_path": m.local_path,
                "currency": m.currency,
                "item_count": m.item_count,
                "extracted": m.extracted,
                "created_at": m.created_at.isoformat(),
                "updated_at": m.updated_at.isoformat(),
            }
            for m in self.repo.list_menus()
        ]
        return self._write("menus.csv", rows)

    def _export_menu_items(self) -> Path:
        rows = [
            {
                "id": i.id,
                "menu_id": i.menu_id,
                "restaurant_id": i.restaurant_id,
                "category": i.category,
                "name": i.name,
                "description": i.description,
                "price": i.price,
                "currency": i.currency,
                "notes": i.notes,
                "availability": i.availability,
                "source_type": i.source_type,
                "created_at": i.created_at.isoformat(),
            }
            for i in self.repo.list_menu_items()
        ]
        return self._write("menu_items.csv", rows)

    def _export_photos(self) -> Path:
        rows = [
            {
                "id": p.id,
                "restaurant_id": p.restaurant_id,
                "source_url": p.source_url,
                "local_path": p.local_path,
                "filename": p.filename,
                "width": p.width,
                "height": p.height,
                "file_size": p.file_size,
                "content_type": p.content_type,
                "is_thumbnail": p.is_thumbnail,
                "downloaded": p.downloaded,
                "download_error": p.download_error,
                "created_at": p.created_at.isoformat(),
            }
            for p in self.repo.list_photos()
        ]
        return self._write("photos.csv", rows)

    def _export_sources(self) -> Path:
        rows = [
            {
                "id": s.id,
                "restaurant_id": s.restaurant_id,
                "source_type": s.source_type,
                "url": s.url,
                "title": s.title,
                "discovered_at": s.discovered_at.isoformat(),
            }
            for s in self.repo.list_sources()
        ]
        return self._write("sources.csv", rows)
