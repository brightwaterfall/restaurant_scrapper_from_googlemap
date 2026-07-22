"""Crawl state persistence for resume support."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from restaurant_crawler.database.repository import RestaurantRepository
from restaurant_crawler.utils.logging import get_logger

logger = get_logger()


class CrawlStateManager:
    def __init__(self, repo: RestaurantRepository, state_file: Path) -> None:
        self.repo = repo
        self.state_file = state_file
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

    def mark_started(self) -> None:
        payload = {
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        self.repo.set_state("crawl_run", payload)
        self._write_file(payload)

    def mark_finished(self, stats: dict[str, Any]) -> None:
        payload = {
            "status": "finished",
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "stats": stats,
        }
        self.repo.set_state("crawl_run", payload)
        self._write_file(payload)

    def mark_interrupted(self, current_id: str | None = None) -> None:
        payload = {
            "status": "interrupted",
            "interrupted_at": datetime.now(timezone.utc).isoformat(),
            "last_restaurant_id": current_id,
        }
        self.repo.set_state("crawl_run", payload)
        self._write_file(payload)

    def load(self) -> dict[str, Any]:
        db_state = self.repo.get_state("crawl_run", {})
        if db_state:
            return db_state
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning("Failed to read state file: {}", exc)
        return {}

    def pending_restaurant_ids(self) -> list[str]:
        return [r.id for r in self.repo.list_pending()]

    def _write_file(self, payload: dict[str, Any]) -> None:
        self.state_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
