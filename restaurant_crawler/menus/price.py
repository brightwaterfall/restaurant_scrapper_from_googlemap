"""Brazilian Real price parsing utilities."""

from __future__ import annotations

import re

PRICE_RE = re.compile(
    r"(?:R\$\s*)?(\d{1,3}(?:\.\d{3})*(?:,\d{2})|\d+(?:[.,]\d{2})?)",
    re.I,
)


def parse_price(text: str | None) -> tuple[float | None, str]:
    if not text:
        return None, "BRL"
    match = PRICE_RE.search(text)
    if not match:
        return None, "BRL"
    raw = match.group(1)
    if "," in raw and "." in raw:
        # 1.234,56
        normalized = raw.replace(".", "").replace(",", ".")
    elif "," in raw:
        normalized = raw.replace(",", ".")
    else:
        normalized = raw
    try:
        return float(normalized), "BRL"
    except ValueError:
        return None, "BRL"


def looks_like_price(text: str) -> bool:
    return bool(re.search(r"R\$|\d+[.,]\d{2}", text))
