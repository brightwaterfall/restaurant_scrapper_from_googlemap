"""Menu and menu-item models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MenuItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    menu_id: str
    restaurant_id: str
    category: str | None = None
    name: str
    description: str | None = None
    price: float | None = None
    currency: str = "BRL"
    notes: str | None = None
    availability: str | None = None
    source_type: str | None = None  # html | pdf | image | ocr
    created_at: datetime = Field(default_factory=utc_now)


class Menu(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    restaurant_id: str
    title: str | None = None
    source_url: str | None = None
    source_type: str = "html"  # html | pdf | image | ocr
    local_path: str | None = None
    currency: str = "BRL"
    item_count: int = 0
    extracted: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    extra: dict[str, Any] = Field(default_factory=dict)

    def touch(self) -> None:
        self.updated_at = utc_now()
