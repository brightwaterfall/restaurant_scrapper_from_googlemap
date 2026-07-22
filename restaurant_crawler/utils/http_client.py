"""Async HTTP client with retries, delays, and robots.txt awareness."""

from __future__ import annotations

import asyncio
import random
from typing import Any
from urllib.parse import urlparse

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from restaurant_crawler.config.settings import Settings
from restaurant_crawler.utils.logging import get_logger
from restaurant_crawler.utils.robots import RobotsCache

logger = get_logger()


class HttpClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.robots = RobotsCache(settings)
        self._client: httpx.AsyncClient | None = None
        self._semaphore = asyncio.Semaphore(settings.max_concurrent)
        self._last_host_request: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> "HttpClient":
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.settings.timeout),
            follow_redirects=True,
            headers={"User-Agent": self._user_agent()},
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _user_agent(self) -> str:
        agents = self.settings.user_agents or [
            "RestaurantCrawler/1.0 (+research; polite bot)"
        ]
        # HTTP header values must be Latin-1/ASCII-safe
        return self._ascii_header(random.choice(agents))

    @staticmethod
    def _ascii_header(value: str) -> str:
        try:
            value.encode("ascii")
            return value
        except UnicodeEncodeError:
            return value.encode("ascii", errors="replace").decode("ascii")

    async def _polite_delay(self, url: str) -> None:
        host = urlparse(url).netloc
        async with self._lock:
            loop = asyncio.get_running_loop()
            now = loop.time()
            last = self._last_host_request.get(host, 0.0)
            wait_for = self.settings.request_delay - (now - last)
            if wait_for > 0:
                await asyncio.sleep(wait_for + random.uniform(0, 0.3))
            self._last_host_request[host] = loop.time()

    async def get(
        self,
        url: str,
        *,
        check_robots: bool = True,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response | None:
        if check_robots and self.settings.respect_robots_txt:
            allowed = await self.robots.can_fetch(url)
            if not allowed:
                logger.warning("Blocked by robots.txt: {}", url)
                return None

        assert self._client is not None
        async with self._semaphore:
            await self._polite_delay(url)
            try:
                async for attempt in AsyncRetrying(
                    stop=stop_after_attempt(self.settings.retry_attempts),
                    wait=wait_exponential(
                        multiplier=1,
                        min=self.settings.retry_min_wait,
                        max=self.settings.retry_max_wait,
                    ),
                    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
                    reraise=True,
                ):
                    with attempt:
                        if attempt.retry_state.attempt_number > 1:
                            logger.warning(
                                "HTTP retry {} GET {}",
                                attempt.retry_state.attempt_number,
                                url,
                            )
                        response = await self._client.get(
                            url,
                            headers={**(headers or {}), "User-Agent": self._user_agent()},
                        )
                        if response.status_code in {429, 500, 502, 503, 504}:
                            response.raise_for_status()
                        logger.debug("GET {} -> {}", url, response.status_code)
                        return response
            except Exception as exc:
                logger.error("GET failed after retries {}: {}", url, exc)
                return None
        return None

    async def get_text(self, url: str, **kwargs: Any) -> str | None:
        response = await self.get(url, **kwargs)
        if response is None or response.status_code >= 400:
            return None
        return response.text

    async def get_bytes(self, url: str, **kwargs: Any) -> bytes | None:
        response = await self.get(url, **kwargs)
        if response is None or response.status_code >= 400:
            return None
        return response.content

    async def post_form(
        self,
        url: str,
        data: dict[str, Any],
        *,
        check_robots: bool = True,
        timeout: float | None = None,
    ) -> httpx.Response | None:
        if check_robots and self.settings.respect_robots_txt:
            allowed = await self.robots.can_fetch(url)
            if not allowed:
                logger.warning("Blocked by robots.txt (POST): {}", url)
                return None

        assert self._client is not None
        request_timeout = httpx.Timeout(timeout or self.settings.timeout)
        async with self._semaphore:
            await self._polite_delay(url)
            try:
                async for attempt in AsyncRetrying(
                    stop=stop_after_attempt(self.settings.retry_attempts),
                    wait=wait_exponential(
                        multiplier=1,
                        min=self.settings.retry_min_wait,
                        max=self.settings.retry_max_wait,
                    ),
                    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
                    reraise=True,
                ):
                    with attempt:
                        response = await self._client.post(
                            url,
                            data=data,
                            headers={"User-Agent": self._user_agent()},
                            timeout=request_timeout,
                        )
                        if response.status_code in {406, 429, 500, 502, 503, 504}:
                            response.raise_for_status()
                        return response
            except Exception as exc:
                logger.error("POST failed after retries {}: {}", url, exc)
                return None
        return None
