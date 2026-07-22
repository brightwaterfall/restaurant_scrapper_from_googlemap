"""Synchronous HTTP helper using requests (fallback / tooling)."""

from __future__ import annotations

import random

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from restaurant_crawler.config.settings import Settings
from restaurant_crawler.utils.logging import get_logger

logger = get_logger()


class SyncHttpClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session = requests.Session()

    def _headers(self) -> dict[str, str]:
        agents = self.settings.user_agents or ["RestaurantCrawler/1.0"]
        agent = random.choice(agents)
        try:
            agent.encode("ascii")
        except UnicodeEncodeError:
            agent = agent.encode("ascii", errors="replace").decode("ascii")
        return {"User-Agent": agent}

    def get(self, url: str) -> requests.Response | None:
        @retry(
            stop=stop_after_attempt(self.settings.retry_attempts),
            wait=wait_exponential(
                multiplier=1,
                min=self.settings.retry_min_wait,
                max=self.settings.retry_max_wait,
            ),
            retry=retry_if_exception_type(requests.RequestException),
            reraise=True,
        )
        def _do() -> requests.Response:
            response = self.session.get(
                url,
                headers=self._headers(),
                timeout=self.settings.timeout,
            )
            if response.status_code in {429, 500, 502, 503, 504}:
                response.raise_for_status()
            return response

        try:
            return _do()
        except Exception as exc:
            logger.error("Sync GET failed {}: {}", url, exc)
            return None

    def close(self) -> None:
        self.session.close()
