"""robots.txt cache and checker."""

from __future__ import annotations

import asyncio
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from restaurant_crawler.config.settings import Settings
from restaurant_crawler.utils.logging import get_logger

logger = get_logger()


class RobotsCache:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._cache: dict[str, RobotFileParser] = {}
        self._lock = asyncio.Lock()

    async def can_fetch(self, url: str) -> bool:
        if not self.settings.respect_robots_txt:
            return True
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return False
        base = f"{parsed.scheme}://{parsed.netloc}"
        parser = await self._get_parser(base)
        if parser is None:
            return True  # fail open if robots unavailable
        user_agent = (
            self.settings.user_agents[0]
            if self.settings.user_agents
            else "RestaurantCrawler"
        )
        return parser.can_fetch(user_agent, url)

    async def _get_parser(self, base: str) -> RobotFileParser | None:
        async with self._lock:
            if base in self._cache:
                return self._cache[base]

        robots_url = f"{base}/robots.txt"
        parser = RobotFileParser()
        try:
            async with httpx.AsyncClient(timeout=self.settings.timeout) as client:
                response = await client.get(robots_url)
                if response.status_code >= 400:
                    logger.debug("No robots.txt at {}", robots_url)
                    async with self._lock:
                        self._cache[base] = parser
                        parser.parse([])
                    return parser
                parser.parse(response.text.splitlines())
        except Exception as exc:
            logger.debug("robots.txt fetch failed for {}: {}", base, exc)
            return None

        async with self._lock:
            self._cache[base] = parser
        return parser
