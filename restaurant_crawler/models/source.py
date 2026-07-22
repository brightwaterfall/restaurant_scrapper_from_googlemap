"""Source attribution and crawl log models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Source(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    restaurant_id: str
    source_type: str  # overpass | website | nominatim | directory | manual
    url: str
    title: str | None = None
    discovered_at: datetime = Field(default_factory=utc_now)
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class CrawlLog(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    restaurant_id: str | None = None
    level: str = "INFO"
    event: str
    message: str
    url: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
