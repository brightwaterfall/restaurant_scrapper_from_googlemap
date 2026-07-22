"""Validate crawled restaurant records and generate reports."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from restaurant_crawler.config.settings import Settings
from restaurant_crawler.database.repository import RestaurantRepository
from restaurant_crawler.models.restaurant import Restaurant
from restaurant_crawler.utils.deduplication import Deduplicator
from restaurant_crawler.utils.logging import get_logger

logger = get_logger()


@dataclass
class ValidationIssue:
    restaurant_id: str
    name: str
    code: str
    message: str
    severity: str = "warning"


@dataclass
class ValidationReport:
    generated_at: str
    total_restaurants: int = 0
    valid_restaurants: int = 0
    issues: list[ValidationIssue] = field(default_factory=list)
    missing_menus: list[str] = field(default_factory=list)
    missing_photos: list[str] = field(default_factory=list)
    missing_addresses: list[str] = field(default_factory=list)
    invalid_coordinates: list[str] = field(default_factory=list)
    duplicates: list[str] = field(default_factory=list)
    success_rate: float = 0.0

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at,
            "total_restaurants": self.total_restaurants,
            "valid_restaurants": self.valid_restaurants,
            "success_rate": self.success_rate,
            "missing_menus": self.missing_menus,
            "missing_photos": self.missing_photos,
            "missing_addresses": self.missing_addresses,
            "invalid_coordinates": self.invalid_coordinates,
            "duplicates": self.duplicates,
            "issues": [i.__dict__ for i in self.issues],
        }


class ValidationPipeline:
    def __init__(self, settings: Settings, repo: RestaurantRepository) -> None:
        self.settings = settings
        self.repo = repo

    def validate(self) -> ValidationReport:
        restaurants = self.repo.list_restaurants()
        report = ValidationReport(
            generated_at=datetime.now(timezone.utc).isoformat(),
            total_restaurants=len(restaurants),
        )
        menus = self.repo.list_menus()
        photos = self.repo.list_photos()
        menu_by_rest = {m.restaurant_id for m in menus if m.item_count > 0}
        photo_by_rest = {p.restaurant_id for p in photos if p.downloaded}

        dedupe = Deduplicator(threshold=self.settings.dedup_threshold)
        for restaurant in restaurants:
            issues = self._validate_one(restaurant, menu_by_rest, photo_by_rest)
            match = dedupe.find_duplicate(restaurant)
            if match.is_duplicate and match.existing and match.existing.id != restaurant.id:
                issues.append(
                    ValidationIssue(
                        restaurant.id,
                        restaurant.name,
                        "duplicate",
                        f"Possible duplicate of {match.existing.name} ({match.score:.1f}% / {match.reason})",
                        "error",
                    )
                )
                report.duplicates.append(restaurant.id)
            else:
                dedupe.register(restaurant)

            for issue in issues:
                report.issues.append(issue)
                if issue.code == "missing_address":
                    report.missing_addresses.append(restaurant.id)
                elif issue.code == "missing_menu":
                    report.missing_menus.append(restaurant.id)
                elif issue.code == "missing_photos":
                    report.missing_photos.append(restaurant.id)
                elif issue.code == "invalid_coordinates":
                    report.invalid_coordinates.append(restaurant.id)

            error_issues = [i for i in issues if i.severity == "error"]
            if not error_issues:
                report.valid_restaurants += 1
                if restaurant.status in {"scraped", "discovered"}:
                    restaurant.status = "validated"
                    self.repo.upsert_restaurant(restaurant)

        if report.total_restaurants:
            report.success_rate = round(
                100.0 * report.valid_restaurants / report.total_restaurants, 2
            )
        logger.info(
            "Validation complete: {}/{} valid ({:.1f}%)",
            report.valid_restaurants,
            report.total_restaurants,
            report.success_rate,
        )
        return report

    def _validate_one(
        self,
        restaurant: Restaurant,
        menu_by_rest: set[str],
        photo_by_rest: set[str],
    ) -> list[ValidationIssue]:
        cfg = self.settings.validation
        issues: list[ValidationIssue] = []

        if cfg.require_address and not restaurant.address:
            issues.append(
                ValidationIssue(
                    restaurant.id,
                    restaurant.name,
                    "missing_address",
                    "Address is missing",
                    "error",
                )
            )

        if cfg.require_coordinates:
            if restaurant.latitude is None or restaurant.longitude is None:
                issues.append(
                    ValidationIssue(
                        restaurant.id,
                        restaurant.name,
                        "invalid_coordinates",
                        "Coordinates are missing",
                        "error",
                    )
                )
            elif cfg.coordinate_bounds_check and not self.settings.geo.contains(
                restaurant.latitude, restaurant.longitude
            ):
                issues.append(
                    ValidationIssue(
                        restaurant.id,
                        restaurant.name,
                        "invalid_coordinates",
                        "Coordinates outside João Pessoa bounding box",
                        "warning",
                    )
                )

        if restaurant.id not in menu_by_rest:
            severity = "error" if cfg.require_menu else "warning"
            issues.append(
                ValidationIssue(
                    restaurant.id,
                    restaurant.name,
                    "missing_menu",
                    "No menu items extracted",
                    severity,
                )
            )

        if restaurant.id not in photo_by_rest:
            severity = "error" if cfg.require_photos else "warning"
            issues.append(
                ValidationIssue(
                    restaurant.id,
                    restaurant.name,
                    "missing_photos",
                    "No photos downloaded",
                    severity,
                )
            )

        return issues
