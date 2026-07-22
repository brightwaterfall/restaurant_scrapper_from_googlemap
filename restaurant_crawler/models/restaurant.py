"""Restaurant and opening-hours models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OpeningHours(BaseModel):
    """Normalized opening hours for a single day or structured block."""

    day: str
    open_time: str | None = None
    close_time: str | None = None
    is_closed: bool = False
    raw: str | None = None


class Restaurant(BaseModel):
    """Canonical restaurant record collected by the crawler."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    address: str | None = None
    city: str = "João Pessoa"
    state: str = "Paraíba"
    country: str = "Brazil"
    latitude: float | None = None
    longitude: float | None = None
    google_maps_url: str | None = None
    website: str | None = None
    phone: str | None = None
    email: str | None = None
    facebook: str | None = None
    instagram: str | None = None
    delivery_platforms: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    opening_hours: list[OpeningHours] = Field(default_factory=list)
    opening_hours_raw: str | None = None
    currency: str = "BRL"
    normalized_name: str | None = None
    normalized_address: str | None = None
    fingerprint: str | None = None
    status: str = "discovered"  # discovered | scraped | validated | failed | skipped
    scrape_error: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    extra: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Restaurant name cannot be empty")
        return cleaned

    @field_validator("website", "facebook", "instagram", "google_maps_url", mode="before")
    @classmethod
    def empty_url_to_none(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        return value

    def touch(self) -> None:
        self.updated_at = utc_now()

    def build_google_maps_url(self) -> str | None:
        if self.google_maps_url:
            return self.google_maps_url
        if self.latitude is not None and self.longitude is not None:
            return (
                "https://www.google.com/maps/search/?api=1"
                f"&query={self.latitude},{self.longitude}"
            )
        if self.name and self.address:
            from urllib.parse import quote_plus

            query = quote_plus(f"{self.name} {self.address} João Pessoa")
            return f"https://www.google.com/maps/search/?api=1&query={query}"
        return None

    def ensure_maps_url(self) -> None:
        if not self.google_maps_url:
            self.google_maps_url = self.build_google_maps_url()
