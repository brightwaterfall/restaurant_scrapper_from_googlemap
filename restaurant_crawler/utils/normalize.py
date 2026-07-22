"""Name/address normalization helpers."""

from __future__ import annotations

import hashlib
import re
import unicodedata


_WHITESPACE = re.compile(r"\s+")
_NON_ALNUM = re.compile(r"[^a-z0-9\s]")
_PHONE_DIGITS = re.compile(r"\D+")

ADDRESS_ABBREVIATIONS = {
    "r.": "rua",
    "rua": "rua",
    "av.": "avenida",
    "av": "avenida",
    "avenida": "avenida",
    "trav.": "travessa",
    "tv.": "travessa",
    "pc.": "praca",
    "pç.": "praca",
    "praca": "praca",
    "praça": "praca",
    "jd.": "jardim",
    "jardim": "jardim",
    "cond.": "condominio",
    "nº": "",
    "n°": "",
    "n.": "",
    "s/n": "sn",
    "joao pessoa": "joao pessoa",
    "joão pessoa": "joao pessoa",
    "pb": "paraiba",
    "paraiba": "paraiba",
    "paraíba": "paraiba",
}


def strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def collapse_whitespace(text: str) -> str:
    return _WHITESPACE.sub(" ", text).strip()


def normalize_name(name: str) -> str:
    text = strip_accents(name.lower())
    text = _NON_ALNUM.sub(" ", text)
    text = collapse_whitespace(text)
    # Drop common legal suffixes
    for suffix in (" ltda", " me", " eireli", " sa", " s a"):
        if text.endswith(suffix):
            text = text[: -len(suffix)].strip()
    return text


def normalize_address(address: str | None) -> str | None:
    if not address:
        return None
    text = strip_accents(address.lower())
    text = text.replace(",", " ")
    text = collapse_whitespace(text)
    parts = []
    for token in text.split(" "):
        mapped = ADDRESS_ABBREVIATIONS.get(token, token)
        if mapped:
            parts.append(mapped)
    return collapse_whitespace(" ".join(parts))


def normalize_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    digits = _PHONE_DIGITS.sub("", phone)
    if len(digits) < 8:
        return None
    return digits


def normalize_website(url: str | None) -> str | None:
    if not url:
        return None
    value = url.strip().lower()
    for prefix in ("https://", "http://"):
        if value.startswith(prefix):
            value = value[len(prefix) :]
    value = value.removeprefix("www.")
    return value.rstrip("/")


def round_coord(value: float | None, precision: int = 5) -> float | None:
    if value is None:
        return None
    return round(float(value), precision)


def make_fingerprint(
    name: str,
    address: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    website: str | None = None,
    phone: str | None = None,
) -> str:
    """Stable fingerprint used for exact-match deduplication."""
    payload = "|".join(
        [
            normalize_name(name),
            normalize_address(address) or "",
            str(round_coord(latitude) or ""),
            str(round_coord(longitude) or ""),
            normalize_website(website) or "",
            normalize_phone(phone) or "",
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
