"""Photo model for restaurant imagery."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Photo(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    restaurant_id: str
    source_url: str
    local_path: str | None = None
    filename: str | None = None
    width: int | None = None
    height: int | None = None
    file_size: int | None = None
    content_type: str | None = None
    is_thumbnail: bool = False
    downloaded: bool = False
    download_error: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
