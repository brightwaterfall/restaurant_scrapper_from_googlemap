"""Smoke test Overpass discovery after encoding fix."""

from __future__ import annotations

import asyncio

from restaurant_crawler.config.settings import reload_settings
from restaurant_crawler.utils.http_client import HttpClient


async def main() -> None:
    settings = reload_settings()
    query = (
        '[out:json][timeout:25];'
        'node["amenity"="restaurant"](-7.13,-34.86,-7.11,-34.84);'
        "out 5;"
    )
    async with HttpClient(settings) as http:
        ua = http._user_agent()
        print("UA:", ua)
        ua.encode("ascii")
        print("UA ascii OK")
        response = await http.post_form(
            settings.discovery.overpass_url,
            {"data": query},
            check_robots=False,
            timeout=60,
        )
        if response is None:
            print("FAIL: no response")
            return
        print("status", response.status_code)
        payload = response.json()
        print("elements", len(payload.get("elements", [])))


if __name__ == "__main__":
    asyncio.run(main())
