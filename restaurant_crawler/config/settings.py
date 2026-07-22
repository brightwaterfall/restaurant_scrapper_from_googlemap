"""Load and validate crawler configuration from config.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"


class GeoBounds(BaseModel):
    south: float
    west: float
    north: float
    east: float
    center_lat: float
    center_lng: float

    def contains(self, lat: float, lng: float) -> bool:
        return self.south <= lat <= self.north and self.west <= lng <= self.east


class DiscoveryConfig(BaseModel):
    use_overpass: bool = True
    overpass_url: str
    overpass_timeout: int = 90
    use_nominatim: bool = True
    nominatim_url: str
    amenity_tags: list[str] = Field(default_factory=list)
    cuisine_nodes: bool = True


class OcrConfig(BaseModel):
    enabled: bool = True
    language: str = "por+eng"
    tesseract_cmd: str | None = None


class ImagesConfig(BaseModel):
    max_per_restaurant: int = 30
    min_width: int = 200
    min_height: int = 200
    prefer_original: bool = True
    concurrent_downloads: int = 4


class ValidationConfig(BaseModel):
    require_address: bool = True
    require_coordinates: bool = True
    require_menu: bool = False
    require_photos: bool = False
    coordinate_bounds_check: bool = True


class EnrichmentConfig(BaseModel):
    enabled: bool = True
    max_queries: int = 4
    max_results_per_query: int = 8
    max_total_results: int = 15
    name_match_threshold: int = 75
    fetch_discovered_pages: bool = True
    enrich_during_crawl: bool = True
    reenrich_missing: bool = True


class Settings(BaseModel):
    city: str
    state: str
    country: str
    city_slug: str = "joao-pessoa"
    geo: GeoBounds
    max_concurrent: int = 5
    timeout: int = 30
    retry_attempts: int = 5
    retry_min_wait: float = 1.0
    retry_max_wait: float = 30.0
    request_delay: float = 1.5
    respect_robots_txt: bool = True
    headless: bool = True
    playwright_timeout_ms: int = 30000
    dedup_threshold: int = 90
    output_folder: str
    database_path: str
    images_folder: str
    menus_folder: str
    logs_folder: str
    state_file: str
    log_level: str = "INFO"
    log_rotation: str = "50 MB"
    log_retention: str = "30 days"
    discovery: DiscoveryConfig
    ocr: OcrConfig = Field(default_factory=OcrConfig)
    images: ImagesConfig = Field(default_factory=ImagesConfig)
    validation: ValidationConfig = Field(default_factory=ValidationConfig)
    enrichment: EnrichmentConfig = Field(default_factory=EnrichmentConfig)
    user_agents: list[str] = Field(default_factory=list)

    @field_validator(
        "output_folder",
        "database_path",
        "images_folder",
        "menus_folder",
        "logs_folder",
        "state_file",
        mode="after",
    )
    @classmethod
    def resolve_path(cls, value: str) -> str:
        path = Path(value)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return str(path.resolve())

    @property
    def project_root(self) -> Path:
        return PROJECT_ROOT

    @property
    def output_path(self) -> Path:
        return Path(self.output_folder)

    @property
    def db_path(self) -> Path:
        return Path(self.database_path)

    @property
    def images_path(self) -> Path:
        return Path(self.images_folder)

    @property
    def menus_path(self) -> Path:
        return Path(self.menus_folder)

    @property
    def logs_path(self) -> Path:
        return Path(self.logs_folder)

    @property
    def state_path(self) -> Path:
        return Path(self.state_file)

    def ensure_directories(self) -> None:
        for path in (
            self.output_path,
            self.db_path.parent,
            self.images_path,
            self.menus_path,
            self.logs_path,
            self.state_path.parent,
        ):
            path.mkdir(parents=True, exist_ok=True)


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config at {path} must be a mapping")
    return data


def build_settings(config_path: Path | None = None) -> Settings:
    path = config_path or DEFAULT_CONFIG_PATH
    raw = load_yaml(path)
    settings = Settings.model_validate(raw)
    settings.ensure_directories()
    return settings


_SETTINGS: Settings | None = None


def get_settings() -> Settings:
    global _SETTINGS
    if _SETTINGS is None:
        _SETTINGS = build_settings()
    return _SETTINGS


def reload_settings(config_path: Path | None = None) -> Settings:
    global _SETTINGS
    _SETTINGS = build_settings(config_path) if config_path else build_settings()
    return _SETTINGS
