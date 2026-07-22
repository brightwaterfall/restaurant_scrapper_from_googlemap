"""Opening hours extraction."""

from __future__ import annotations

import json
import re
from typing import Any

from bs4 import BeautifulSoup

from restaurant_crawler.models.restaurant import OpeningHours

DAY_MAP = {
    "monday": "monday",
    "tuesday": "tuesday",
    "wednesday": "wednesday",
    "thursday": "thursday",
    "friday": "friday",
    "saturday": "saturday",
    "sunday": "sunday",
    "segunda": "monday",
    "terça": "tuesday",
    "terca": "tuesday",
    "quarta": "wednesday",
    "quinta": "thursday",
    "sexta": "friday",
    "sábado": "saturday",
    "sabado": "saturday",
    "domingo": "sunday",
}


def extract_opening_hours(soup: BeautifulSoup) -> tuple[list[OpeningHours], str | None]:
    # JSON-LD
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except Exception:
            continue
        hours = _from_jsonld(data)
        if hours:
            raw = "; ".join(f"{h.day}: {h.open_time}-{h.close_time}" for h in hours if h.open_time)
            return hours, raw

    # Microdata / common classes
    for selector in (
        "[itemprop='openingHours']",
        ".opening-hours",
        ".horario",
        ".horarios",
        "#horario",
    ):
        nodes = soup.select(selector)
        if nodes:
            raw = " | ".join(n.get_text(" ", strip=True) for n in nodes if n.get_text(strip=True))
            if raw:
                return _parse_freeform(raw), raw

    text = soup.get_text("\n", strip=True)
    match = re.search(
        r"(hor[aá]rio[s]?[^:\n]*[:\n].{10,200})",
        text,
        re.I | re.S,
    )
    if match:
        raw = re.sub(r"\s+", " ", match.group(1)).strip()
        return _parse_freeform(raw), raw
    return [], None


def _from_jsonld(data: Any) -> list[OpeningHours]:
    items = data if isinstance(data, list) else [data]
    results: list[OpeningHours] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if "@graph" in item:
            results.extend(_from_jsonld(item["@graph"]))
            continue
        specs = item.get("openingHoursSpecification") or item.get("openingHours")
        if isinstance(specs, str):
            results.extend(_parse_freeform(specs))
        elif isinstance(specs, list):
            for spec in specs:
                if isinstance(spec, str):
                    results.extend(_parse_freeform(spec))
                elif isinstance(spec, dict):
                    days = spec.get("dayOfWeek", [])
                    if isinstance(days, str):
                        days = [days]
                    opens = spec.get("opens")
                    closes = spec.get("closes")
                    for day in days:
                        day_name = str(day).split("/")[-1].lower()
                        results.append(
                            OpeningHours(
                                day=DAY_MAP.get(day_name, day_name),
                                open_time=opens,
                                close_time=closes,
                            )
                        )
    return results


def _parse_freeform(raw: str) -> list[OpeningHours]:
    results: list[OpeningHours] = []
    for day_pt, day_en in DAY_MAP.items():
        pattern = re.compile(
            rf"{day_pt}\s*[:\-]?\s*(\d{{1,2}}[:h]\d{{2}})\s*[-–àsAate]+\s*(\d{{1,2}}[:h]\d{{2}})",
            re.I,
        )
        match = pattern.search(raw)
        if match:
            results.append(
                OpeningHours(
                    day=day_en,
                    open_time=match.group(1).replace("h", ":"),
                    close_time=match.group(2).replace("h", ":"),
                    raw=match.group(0),
                )
            )
    if not results:
        results.append(OpeningHours(day="all", raw=raw))
    return results
