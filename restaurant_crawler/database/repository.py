"""CRUD repository for crawler entities."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from restaurant_crawler.database.connection import Database
from restaurant_crawler.models.menu import Menu, MenuItem
from restaurant_crawler.models.photo import Photo
from restaurant_crawler.models.restaurant import OpeningHours, Restaurant
from restaurant_crawler.models.source import CrawlLog, Source


def _dt(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    return json.loads(value)


class RestaurantRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Restaurants
    # ------------------------------------------------------------------
    def upsert_restaurant(self, restaurant: Restaurant) -> Restaurant:
        restaurant.ensure_maps_url()
        restaurant.touch()
        self.db.execute(
            """
            INSERT INTO restaurants (
                id, name, address, city, state, country, latitude, longitude,
                google_maps_url, website, phone, email, facebook, instagram,
                delivery_platforms, categories, opening_hours, opening_hours_raw,
                currency, normalized_name, normalized_address, fingerprint,
                status, scrape_error, extra, created_at, updated_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                address=excluded.address,
                city=excluded.city,
                state=excluded.state,
                country=excluded.country,
                latitude=excluded.latitude,
                longitude=excluded.longitude,
                google_maps_url=excluded.google_maps_url,
                website=excluded.website,
                phone=excluded.phone,
                email=excluded.email,
                facebook=excluded.facebook,
                instagram=excluded.instagram,
                delivery_platforms=excluded.delivery_platforms,
                categories=excluded.categories,
                opening_hours=excluded.opening_hours,
                opening_hours_raw=excluded.opening_hours_raw,
                currency=excluded.currency,
                normalized_name=excluded.normalized_name,
                normalized_address=excluded.normalized_address,
                fingerprint=excluded.fingerprint,
                status=excluded.status,
                scrape_error=excluded.scrape_error,
                extra=excluded.extra,
                updated_at=excluded.updated_at
            """,
            (
                restaurant.id,
                restaurant.name,
                restaurant.address,
                restaurant.city,
                restaurant.state,
                restaurant.country,
                restaurant.latitude,
                restaurant.longitude,
                restaurant.google_maps_url,
                restaurant.website,
                restaurant.phone,
                restaurant.email,
                restaurant.facebook,
                restaurant.instagram,
                _json_dumps(restaurant.delivery_platforms),
                _json_dumps(restaurant.categories),
                _json_dumps([h.model_dump() for h in restaurant.opening_hours]),
                restaurant.opening_hours_raw,
                restaurant.currency,
                restaurant.normalized_name,
                restaurant.normalized_address,
                restaurant.fingerprint,
                restaurant.status,
                restaurant.scrape_error,
                _json_dumps(restaurant.extra),
                _dt(restaurant.created_at),
                _dt(restaurant.updated_at),
            ),
        )
        return restaurant

    def get_restaurant(self, restaurant_id: str) -> Restaurant | None:
        row = self.db.fetchone("SELECT * FROM restaurants WHERE id = ?", (restaurant_id,))
        return self._row_to_restaurant(row) if row else None

    def get_by_fingerprint(self, fingerprint: str) -> Restaurant | None:
        row = self.db.fetchone(
            "SELECT * FROM restaurants WHERE fingerprint = ?", (fingerprint,)
        )
        return self._row_to_restaurant(row) if row else None

    def list_restaurants(self, status: str | None = None) -> list[Restaurant]:
        if status:
            rows = self.db.fetchall(
                "SELECT * FROM restaurants WHERE status = ? ORDER BY name", (status,)
            )
        else:
            rows = self.db.fetchall("SELECT * FROM restaurants ORDER BY name")
        return [self._row_to_restaurant(r) for r in rows]

    def list_pending(self) -> list[Restaurant]:
        rows = self.db.fetchall(
            """
            SELECT * FROM restaurants
            WHERE status IN ('discovered', 'failed')
            ORDER BY created_at
            """
        )
        return [self._row_to_restaurant(r) for r in rows]

    def count_restaurants(self) -> int:
        row = self.db.fetchone("SELECT COUNT(*) AS c FROM restaurants")
        return int(row["c"]) if row else 0

    def _row_to_restaurant(self, row: Any) -> Restaurant:
        hours_raw = _json_loads(row["opening_hours"], [])
        hours = [OpeningHours.model_validate(h) for h in hours_raw]
        return Restaurant(
            id=row["id"],
            name=row["name"],
            address=row["address"],
            city=row["city"] or "João Pessoa",
            state=row["state"] or "Paraíba",
            country=row["country"] or "Brazil",
            latitude=row["latitude"],
            longitude=row["longitude"],
            google_maps_url=row["google_maps_url"],
            website=row["website"],
            phone=row["phone"],
            email=row["email"],
            facebook=row["facebook"],
            instagram=row["instagram"],
            delivery_platforms=_json_loads(row["delivery_platforms"], []),
            categories=_json_loads(row["categories"], []),
            opening_hours=hours,
            opening_hours_raw=row["opening_hours_raw"],
            currency=row["currency"] or "BRL",
            normalized_name=row["normalized_name"],
            normalized_address=row["normalized_address"],
            fingerprint=row["fingerprint"],
            status=row["status"] or "discovered",
            scrape_error=row["scrape_error"],
            created_at=_parse_dt(row["created_at"]) or datetime.now(timezone.utc),
            updated_at=_parse_dt(row["updated_at"]) or datetime.now(timezone.utc),
            extra=_json_loads(row["extra"], {}),
        )

    # ------------------------------------------------------------------
    # Menus / items
    # ------------------------------------------------------------------
    def upsert_menu(self, menu: Menu) -> Menu:
        menu.touch()
        self.db.execute(
            """
            INSERT INTO menus (
                id, restaurant_id, title, source_url, source_type, local_path,
                currency, item_count, extracted, extra, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title=excluded.title,
                source_url=excluded.source_url,
                source_type=excluded.source_type,
                local_path=excluded.local_path,
                currency=excluded.currency,
                item_count=excluded.item_count,
                extracted=excluded.extracted,
                extra=excluded.extra,
                updated_at=excluded.updated_at
            """,
            (
                menu.id,
                menu.restaurant_id,
                menu.title,
                menu.source_url,
                menu.source_type,
                menu.local_path,
                menu.currency,
                menu.item_count,
                1 if menu.extracted else 0,
                _json_dumps(menu.extra),
                _dt(menu.created_at),
                _dt(menu.updated_at),
            ),
        )
        return menu

    def insert_menu_items(self, items: list[MenuItem]) -> None:
        if not items:
            return
        self.db.executemany(
            """
            INSERT OR REPLACE INTO menu_items (
                id, menu_id, restaurant_id, category, name, description,
                price, currency, notes, availability, source_type, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    i.id,
                    i.menu_id,
                    i.restaurant_id,
                    i.category,
                    i.name,
                    i.description,
                    i.price,
                    i.currency,
                    i.notes,
                    i.availability,
                    i.source_type,
                    _dt(i.created_at),
                )
                for i in items
            ],
        )

    def list_menus(self, restaurant_id: str | None = None) -> list[Menu]:
        if restaurant_id:
            rows = self.db.fetchall(
                "SELECT * FROM menus WHERE restaurant_id = ?", (restaurant_id,)
            )
        else:
            rows = self.db.fetchall("SELECT * FROM menus")
        return [self._row_to_menu(r) for r in rows]

    def list_menu_items(self, restaurant_id: str | None = None) -> list[MenuItem]:
        if restaurant_id:
            rows = self.db.fetchall(
                "SELECT * FROM menu_items WHERE restaurant_id = ?", (restaurant_id,)
            )
        else:
            rows = self.db.fetchall("SELECT * FROM menu_items")
        return [self._row_to_menu_item(r) for r in rows]

    def delete_menu_items_for_menu(self, menu_id: str) -> None:
        self.db.execute("DELETE FROM menu_items WHERE menu_id = ?", (menu_id,))

    def _row_to_menu(self, row: Any) -> Menu:
        return Menu(
            id=row["id"],
            restaurant_id=row["restaurant_id"],
            title=row["title"],
            source_url=row["source_url"],
            source_type=row["source_type"] or "html",
            local_path=row["local_path"],
            currency=row["currency"] or "BRL",
            item_count=row["item_count"] or 0,
            extracted=bool(row["extracted"]),
            created_at=_parse_dt(row["created_at"]) or datetime.now(timezone.utc),
            updated_at=_parse_dt(row["updated_at"]) or datetime.now(timezone.utc),
            extra=_json_loads(row["extra"], {}),
        )

    def _row_to_menu_item(self, row: Any) -> MenuItem:
        return MenuItem(
            id=row["id"],
            menu_id=row["menu_id"],
            restaurant_id=row["restaurant_id"],
            category=row["category"],
            name=row["name"],
            description=row["description"],
            price=row["price"],
            currency=row["currency"] or "BRL",
            notes=row["notes"],
            availability=row["availability"],
            source_type=row["source_type"],
            created_at=_parse_dt(row["created_at"]) or datetime.now(timezone.utc),
        )

    # ------------------------------------------------------------------
    # Photos / sources / logs
    # ------------------------------------------------------------------
    def upsert_photo(self, photo: Photo) -> Photo:
        self.db.execute(
            """
            INSERT INTO photos (
                id, restaurant_id, source_url, local_path, filename, width, height,
                file_size, content_type, is_thumbnail, downloaded, download_error, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                local_path=excluded.local_path,
                filename=excluded.filename,
                width=excluded.width,
                height=excluded.height,
                file_size=excluded.file_size,
                content_type=excluded.content_type,
                is_thumbnail=excluded.is_thumbnail,
                downloaded=excluded.downloaded,
                download_error=excluded.download_error
            """,
            (
                photo.id,
                photo.restaurant_id,
                photo.source_url,
                photo.local_path,
                photo.filename,
                photo.width,
                photo.height,
                photo.file_size,
                photo.content_type,
                1 if photo.is_thumbnail else 0,
                1 if photo.downloaded else 0,
                photo.download_error,
                _dt(photo.created_at),
            ),
        )
        return photo

    def list_photos(self, restaurant_id: str | None = None) -> list[Photo]:
        if restaurant_id:
            rows = self.db.fetchall(
                "SELECT * FROM photos WHERE restaurant_id = ?", (restaurant_id,)
            )
        else:
            rows = self.db.fetchall("SELECT * FROM photos")
        return [self._row_to_photo(r) for r in rows]

    def list_undownloaded_photos(self) -> list[Photo]:
        rows = self.db.fetchall("SELECT * FROM photos WHERE downloaded = 0")
        return [self._row_to_photo(r) for r in rows]

    def _row_to_photo(self, row: Any) -> Photo:
        return Photo(
            id=row["id"],
            restaurant_id=row["restaurant_id"],
            source_url=row["source_url"],
            local_path=row["local_path"],
            filename=row["filename"],
            width=row["width"],
            height=row["height"],
            file_size=row["file_size"],
            content_type=row["content_type"],
            is_thumbnail=bool(row["is_thumbnail"]),
            downloaded=bool(row["downloaded"]),
            download_error=row["download_error"],
            created_at=_parse_dt(row["created_at"]) or datetime.now(timezone.utc),
        )

    def insert_source(self, source: Source) -> Source:
        self.db.execute(
            """
            INSERT OR REPLACE INTO sources (
                id, restaurant_id, source_type, url, title, discovered_at, raw_payload
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source.id,
                source.restaurant_id,
                source.source_type,
                source.url,
                source.title,
                _dt(source.discovered_at),
                _json_dumps(source.raw_payload),
            ),
        )
        return source

    def list_sources(self, restaurant_id: str | None = None) -> list[Source]:
        if restaurant_id:
            rows = self.db.fetchall(
                "SELECT * FROM sources WHERE restaurant_id = ?", (restaurant_id,)
            )
        else:
            rows = self.db.fetchall("SELECT * FROM sources")
        return [
            Source(
                id=r["id"],
                restaurant_id=r["restaurant_id"],
                source_type=r["source_type"],
                url=r["url"],
                title=r["title"],
                discovered_at=_parse_dt(r["discovered_at"]) or datetime.now(timezone.utc),
                raw_payload=_json_loads(r["raw_payload"], {}),
            )
            for r in rows
        ]

    def insert_log(self, log: CrawlLog) -> None:
        self.db.execute(
            """
            INSERT INTO crawl_logs (
                id, restaurant_id, level, event, message, url, details, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                log.id,
                log.restaurant_id,
                log.level,
                log.event,
                log.message,
                log.url,
                _json_dumps(log.details),
                _dt(log.created_at),
            ),
        )

    def list_logs(self, limit: int = 1000) -> list[CrawlLog]:
        rows = self.db.fetchall(
            "SELECT * FROM crawl_logs ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        return [
            CrawlLog(
                id=r["id"],
                restaurant_id=r["restaurant_id"],
                level=r["level"] or "INFO",
                event=r["event"],
                message=r["message"],
                url=r["url"],
                details=_json_loads(r["details"], {}),
                created_at=_parse_dt(r["created_at"]) or datetime.now(timezone.utc),
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Crawl state (resume)
    # ------------------------------------------------------------------
    def set_state(self, key: str, value: Any) -> None:
        self.db.execute(
            """
            INSERT INTO crawl_state (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
            """,
            (key, _json_dumps(value), datetime.now(timezone.utc).isoformat()),
        )

    def get_state(self, key: str, default: Any = None) -> Any:
        row = self.db.fetchone("SELECT value FROM crawl_state WHERE key = ?", (key,))
        if not row:
            return default
        return _json_loads(row["value"], default)

    def stats(self) -> dict[str, int]:
        def _count(table: str, where: str = "") -> int:
            sql = f"SELECT COUNT(*) AS c FROM {table}"
            if where:
                sql += f" WHERE {where}"
            row = self.db.fetchone(sql)
            return int(row["c"]) if row else 0

        return {
            "restaurants": _count("restaurants"),
            "menus": _count("menus"),
            "menu_items": _count("menu_items"),
            "photos": _count("photos"),
            "photos_downloaded": _count("photos", "downloaded = 1"),
            "sources": _count("sources"),
            "failed": _count("restaurants", "status = 'failed'"),
            "scraped": _count("restaurants", "status = 'scraped'"),
            "validated": _count("restaurants", "status = 'validated'"),
            "discovered": _count("restaurants", "status = 'discovered'"),
        }
