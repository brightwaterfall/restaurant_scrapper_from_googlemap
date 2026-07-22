"""Restaurant deduplication with RapidFuzz."""

from __future__ import annotations

from dataclasses import dataclass

from rapidfuzz import fuzz

from restaurant_crawler.models.restaurant import Restaurant
from restaurant_crawler.utils.normalize import (
    make_fingerprint,
    normalize_address,
    normalize_name,
    normalize_phone,
    normalize_website,
    round_coord,
)


@dataclass
class MatchResult:
    is_duplicate: bool
    existing: Restaurant | None
    score: float
    reason: str


class Deduplicator:
    """In-memory + fuzzy matching against known restaurants."""

    def __init__(self, threshold: int = 90) -> None:
        self.threshold = threshold
        self._by_fingerprint: dict[str, Restaurant] = {}
        self._restaurants: list[Restaurant] = []

    def load(self, restaurants: list[Restaurant]) -> None:
        for restaurant in restaurants:
            self.register(restaurant)

    def register(self, restaurant: Restaurant) -> None:
        if not restaurant.fingerprint:
            restaurant.fingerprint = make_fingerprint(
                restaurant.name,
                restaurant.address,
                restaurant.latitude,
                restaurant.longitude,
                restaurant.website,
                restaurant.phone,
            )
        restaurant.normalized_name = normalize_name(restaurant.name)
        restaurant.normalized_address = normalize_address(restaurant.address)
        self._by_fingerprint[restaurant.fingerprint] = restaurant
        self._restaurants.append(restaurant)

    def find_duplicate(self, candidate: Restaurant) -> MatchResult:
        fingerprint = make_fingerprint(
            candidate.name,
            candidate.address,
            candidate.latitude,
            candidate.longitude,
            candidate.website,
            candidate.phone,
        )
        candidate.fingerprint = fingerprint
        candidate.normalized_name = normalize_name(candidate.name)
        candidate.normalized_address = normalize_address(candidate.address)

        exact = self._by_fingerprint.get(fingerprint)
        if exact:
            return MatchResult(True, exact, 100.0, "fingerprint")

        # Exact website / phone matches
        cand_web = normalize_website(candidate.website)
        cand_phone = normalize_phone(candidate.phone)
        for existing in self._restaurants:
            if cand_web and normalize_website(existing.website) == cand_web:
                return MatchResult(True, existing, 100.0, "website")
            if cand_phone and normalize_phone(existing.phone) == cand_phone:
                # phone alone is strong but verify name similarity
                name_score = fuzz.token_sort_ratio(
                    candidate.normalized_name or "",
                    existing.normalized_name or "",
                )
                if name_score >= self.threshold - 10:
                    return MatchResult(True, existing, float(name_score), "phone+name")

        # Coordinate proximity + name
        if candidate.latitude is not None and candidate.longitude is not None:
            for existing in self._restaurants:
                if existing.latitude is None or existing.longitude is None:
                    continue
                if (
                    abs(existing.latitude - candidate.latitude) < 0.0003
                    and abs(existing.longitude - candidate.longitude) < 0.0003
                ):
                    name_score = fuzz.token_sort_ratio(
                        candidate.normalized_name or "",
                        existing.normalized_name or "",
                    )
                    if name_score >= self.threshold - 5:
                        return MatchResult(True, existing, float(name_score), "geo+name")

        # Fuzzy name + address
        best: MatchResult | None = None
        for existing in self._restaurants:
            name_score = fuzz.token_sort_ratio(
                candidate.normalized_name or "",
                existing.normalized_name or "",
            )
            addr_score = 0.0
            if candidate.normalized_address and existing.normalized_address:
                addr_score = fuzz.token_sort_ratio(
                    candidate.normalized_address,
                    existing.normalized_address,
                )
            combined = (name_score * 0.65) + (addr_score * 0.35) if addr_score else name_score
            if combined >= self.threshold:
                result = MatchResult(True, existing, float(combined), "fuzzy")
                if best is None or result.score > best.score:
                    best = result

        if best:
            return best
        return MatchResult(False, None, 0.0, "unique")

    def merge(self, existing: Restaurant, incoming: Restaurant) -> Restaurant:
        """Fill missing fields on existing from incoming."""
        for field in (
            "address",
            "latitude",
            "longitude",
            "google_maps_url",
            "website",
            "phone",
            "email",
            "facebook",
            "instagram",
            "opening_hours_raw",
        ):
            if getattr(existing, field) in (None, "") and getattr(incoming, field):
                setattr(existing, field, getattr(incoming, field))

        for field in ("delivery_platforms", "categories"):
            current = list(getattr(existing, field) or [])
            for item in getattr(incoming, field) or []:
                if item not in current:
                    current.append(item)
            setattr(existing, field, current)

        if incoming.opening_hours and not existing.opening_hours:
            existing.opening_hours = incoming.opening_hours

        existing.ensure_maps_url()
        existing.fingerprint = make_fingerprint(
            existing.name,
            existing.address,
            existing.latitude,
            existing.longitude,
            existing.website,
            existing.phone,
        )
        existing.touch()
        return existing
