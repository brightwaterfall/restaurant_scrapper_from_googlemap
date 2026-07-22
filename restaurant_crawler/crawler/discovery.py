"""Discover restaurants from public OpenStreetMap / Nominatim sources."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus

from restaurant_crawler.config.settings import Settings
from restaurant_crawler.models.restaurant import Restaurant
from restaurant_crawler.models.source import Source
from restaurant_crawler.utils.http_client import HttpClient
from restaurant_crawler.utils.logging import get_logger
from restaurant_crawler.utils.normalize import make_fingerprint, normalize_address, normalize_name

logger = get_logger()


class RestaurantDiscovery:
    """Discover publicly mapped restaurants in João Pessoa via Overpass API."""

    def __init__(self, settings: Settings, http: HttpClient) -> None:
        self.settings = settings
        self.http = http

    def _overpass_query(self) -> str:
        geo = self.settings.geo
        amenities = self.settings.discovery.amenity_tags
        amenity_regex = "|".join(amenities)
        bbox = f"{geo.south},{geo.west},{geo.north},{geo.east}"
        return f"""
[out:json][timeout:{self.settings.discovery.overpass_timeout}];
(
  node["amenity"~"{amenity_regex}"]({bbox});
  way["amenity"~"{amenity_regex}"]({bbox});
  relation["amenity"~"{amenity_regex}"]({bbox});
  node["shop"="bakery"]({bbox});
  way["shop"="bakery"]({bbox});
);
out center tags;
"""

    async def discover_overpass(self) -> list[tuple[Restaurant, Source]]:
        if not self.settings.discovery.use_overpass:
            return []

        query = self._overpass_query()
        logger.info("Querying Overpass API for restaurants in {}", self.settings.city)
        response = await self.http.post_form(
            self.settings.discovery.overpass_url,
            {"data": query},
            check_robots=False,
            timeout=float(self.settings.discovery.overpass_timeout),
        )
        if response is None:
            logger.error("Overpass discovery failed")
            return []

        try:
            payload = response.json()
        except Exception as exc:
            logger.error("Invalid Overpass JSON: {}", exc)
            return []

        elements = payload.get("elements", [])
        logger.info("Overpass returned {} elements", len(elements))
        results: list[tuple[Restaurant, Source]] = []
        for element in elements:
            restaurant = self._element_to_restaurant(element)
            if restaurant is None:
                continue
            osm_type = element.get("type", "node")
            osm_id = element.get("id")
            source = Source(
                restaurant_id=restaurant.id,
                source_type="overpass",
                url=f"https://www.openstreetmap.org/{osm_type}/{osm_id}",
                title=f"OSM {osm_type}/{osm_id}",
                raw_payload={"tags": element.get("tags", {}), "id": osm_id, "type": osm_type},
            )
            results.append((restaurant, source))
        return results

    def _element_to_restaurant(self, element: dict[str, Any]) -> Restaurant | None:
        tags = element.get("tags") or {}
        name = tags.get("name") or tags.get("name:pt") or tags.get("official_name")
        if not name:
            return None

        lat = element.get("lat")
        lon = element.get("lon")
        if lat is None or lon is None:
            center = element.get("center") or {}
            lat = center.get("lat")
            lon = center.get("lon")

        address = self._build_address(tags)
        website = tags.get("website") or tags.get("contact:website") or tags.get("url")
        phone = tags.get("phone") or tags.get("contact:phone") or tags.get("mobile")
        email = tags.get("email") or tags.get("contact:email")
        facebook = tags.get("facebook") or tags.get("contact:facebook")
        instagram = tags.get("instagram") or tags.get("contact:instagram")
        cuisine = tags.get("cuisine")
        categories = []
        if tags.get("amenity"):
            categories.append(tags["amenity"])
        if cuisine:
            categories.extend([c.strip() for c in cuisine.split(";") if c.strip()])

        hours = tags.get("opening_hours")
        delivery = []
        if tags.get("delivery") in {"yes", "only"}:
            delivery.append("delivery")
        if tags.get("takeaway") == "yes":
            delivery.append("takeaway")

        restaurant = Restaurant(
            name=name.strip(),
            address=address,
            city=self.settings.city,
            state=self.settings.state,
            country=self.settings.country,
            latitude=float(lat) if lat is not None else None,
            longitude=float(lon) if lon is not None else None,
            website=website,
            phone=phone,
            email=email,
            facebook=self._normalize_social(facebook, "facebook.com"),
            instagram=self._normalize_social(instagram, "instagram.com"),
            delivery_platforms=delivery,
            categories=categories,
            opening_hours_raw=hours,
            currency="BRL",
            status="discovered",
            extra={"osm_id": element.get("id"), "osm_type": element.get("type")},
        )
        restaurant.normalized_name = normalize_name(restaurant.name)
        restaurant.normalized_address = normalize_address(restaurant.address)
        restaurant.fingerprint = make_fingerprint(
            restaurant.name,
            restaurant.address,
            restaurant.latitude,
            restaurant.longitude,
            restaurant.website,
            restaurant.phone,
        )
        restaurant.ensure_maps_url()
        return restaurant

    def _build_address(self, tags: dict[str, str]) -> str | None:
        if tags.get("addr:full"):
            return tags["addr:full"]
        parts = [
            tags.get("addr:street"),
            tags.get("addr:housenumber"),
            tags.get("addr:suburb") or tags.get("addr:neighbourhood"),
            tags.get("addr:city") or self.settings.city,
            tags.get("addr:state") or "PB",
            tags.get("addr:postcode"),
        ]
        cleaned = [p for p in parts if p]
        if not cleaned:
            return None
        return ", ".join(cleaned)

    @staticmethod
    def _normalize_social(value: str | None, domain: str) -> str | None:
        if not value:
            return None
        value = value.strip()
        if value.startswith("http"):
            return value
        if value.startswith("@"):
            handle = value[1:]
            return f"https://www.{domain}/{handle}"
        if domain in value:
            return f"https://{value.lstrip('/')}"
        return f"https://www.{domain}/{value.lstrip('/')}"

    async def enrich_with_nominatim(
        self, restaurants: list[Restaurant], limit: int = 50
    ) -> list[Restaurant]:
        """Optionally fill missing addresses via Nominatim reverse geocoding."""
        if not self.settings.discovery.use_nominatim:
            return restaurants

        enriched = 0
        for restaurant in restaurants:
            if restaurant.address or restaurant.latitude is None or restaurant.longitude is None:
                continue
            if enriched >= limit:
                break
            url = (
                f"{self.settings.discovery.nominatim_url}/reverse"
                f"?lat={restaurant.latitude}&lon={restaurant.longitude}"
                f"&format=json&addressdetails=1"
            )
            response = await self.http.get(url, check_robots=True)
            if response is None or response.status_code >= 400:
                continue
            try:
                data = response.json()
            except Exception:
                continue
            display = data.get("display_name")
            if display:
                restaurant.address = display
                restaurant.normalized_address = normalize_address(display)
                enriched += 1
        logger.info("Nominatim enriched {} addresses", enriched)
        return restaurants

    @staticmethod
    def google_maps_search_url(name: str, address: str | None = None) -> str:
        query = quote_plus(f"{name} {address or ''} João Pessoa PB".strip())
        return f"https://www.google.com/maps/search/?api=1&query={query}"
