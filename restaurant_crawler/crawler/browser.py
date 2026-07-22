"""Playwright-backed browser fetcher for dynamic sites."""

from __future__ import annotations

import asyncio
from typing import Any

from restaurant_crawler.config.settings import Settings
from restaurant_crawler.utils.logging import get_logger

logger = get_logger()


class BrowserFetcher:
    """Lazy Playwright browser for dynamic HTML and infinite scroll."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._playwright: Any = None
        self._browser: Any = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        async with self._lock:
            if self._browser is not None:
                return
            try:
                from playwright.async_api import async_playwright
            except ImportError as exc:
                raise RuntimeError(
                    "Playwright is not installed. Run: pip install playwright && playwright install chromium"
                ) from exc

            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self.settings.headless
            )
            logger.info("Playwright browser started (headless={})", self.settings.headless)

    async def close(self) -> None:
        async with self._lock:
            if self._browser is not None:
                await self._browser.close()
                self._browser = None
            if self._playwright is not None:
                await self._playwright.stop()
                self._playwright = None

    async def fetch_html(
        self,
        url: str,
        *,
        scroll: bool = False,
        max_scrolls: int = 10,
        wait_selector: str | None = None,
    ) -> str | None:
        await self.start()
        assert self._browser is not None
        context = await self._browser.new_context(
            user_agent=(
                self.settings.user_agents[0]
                if self.settings.user_agents
                else "RestaurantCrawler/1.0"
            ),
            locale="pt-BR",
        )
        page = await context.new_page()
        try:
            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=self.settings.playwright_timeout_ms,
            )
            if wait_selector:
                try:
                    await page.wait_for_selector(
                        wait_selector, timeout=self.settings.playwright_timeout_ms
                    )
                except Exception:
                    logger.debug("wait_selector timeout for {}", url)

            if scroll:
                await self._auto_scroll(page, max_scrolls=max_scrolls)

            # Trigger lazy images
            await page.evaluate(
                """
                () => {
                  document.querySelectorAll('img[data-src], img[data-lazy], img[loading="lazy"]')
                    .forEach(img => {
                      const src = img.getAttribute('data-src') || img.getAttribute('data-lazy');
                      if (src) img.setAttribute('src', src);
                    });
                }
                """
            )
            await page.wait_for_timeout(500)
            return await page.content()
        except Exception as exc:
            logger.error("Playwright fetch failed for {}: {}", url, exc)
            return None
        finally:
            await context.close()

    async def _auto_scroll(self, page: Any, max_scrolls: int = 10) -> None:
        last_height = 0
        for _ in range(max_scrolls):
            height = await page.evaluate("() => document.body.scrollHeight")
            if height == last_height:
                break
            last_height = height
            await page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(800)
            # Click common "load more" buttons if present
            for selector in (
                "button:has-text('Carregar')",
                "button:has-text('Load more')",
                "a:has-text('Mais')",
                ".load-more",
            ):
                try:
                    btn = page.locator(selector).first
                    if await btn.count() > 0 and await btn.is_visible():
                        await btn.click(timeout=1000)
                        await page.wait_for_timeout(800)
                except Exception:
                    continue
