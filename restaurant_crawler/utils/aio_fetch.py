"""aiohttp-based concurrent byte fetcher (used for bulk asset downloads)."""

from __future__ import annotations

import asyncio
from typing import Iterable

import aiohttp

from restaurant_crawler.utils.logging import get_logger

logger = get_logger()


async def fetch_many(
    urls: Iterable[str],
    *,
    timeout: int = 30,
    concurrency: int = 4,
    user_agent: str = "RestaurantCrawler/1.0",
) -> dict[str, bytes | None]:
    semaphore = asyncio.Semaphore(concurrency)
    results: dict[str, bytes | None] = {}
    timeout_cfg = aiohttp.ClientTimeout(total=timeout)

    async with aiohttp.ClientSession(
        timeout=timeout_cfg,
        headers={"User-Agent": user_agent},
    ) as session:

        async def one(url: str) -> None:
            async with semaphore:
                try:
                    async with session.get(url) as response:
                        if response.status >= 400:
                            results[url] = None
                            return
                        results[url] = await response.read()
                except Exception as exc:
                    logger.debug("aiohttp fetch failed {}: {}", url, exc)
                    results[url] = None

        await asyncio.gather(*[one(url) for url in urls])
    return results
