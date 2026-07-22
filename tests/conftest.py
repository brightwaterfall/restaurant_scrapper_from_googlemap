"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from restaurant_crawler.config.settings import Settings, build_settings
from restaurant_crawler.database.connection import Database
from restaurant_crawler.database.repository import RestaurantRepository


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    config = {
        "city": "João Pessoa",
        "state": "Paraíba",
        "country": "Brazil",
        "city_slug": "joao-pessoa",
        "geo": {
            "south": -7.25,
            "west": -34.95,
            "north": -7.05,
            "east": -34.75,
            "center_lat": -7.1195,
            "center_lng": -34.8450,
        },
        "max_concurrent": 2,
        "timeout": 10,
        "retry_attempts": 2,
        "retry_min_wait": 0.1,
        "retry_max_wait": 0.5,
        "request_delay": 0.0,
        "respect_robots_txt": False,
        "headless": True,
        "playwright_timeout_ms": 5000,
        "dedup_threshold": 90,
        "output_folder": str(tmp_path / "exports"),
        "database_path": str(tmp_path / "test.db"),
        "images_folder": str(tmp_path / "images"),
        "menus_folder": str(tmp_path / "menus"),
        "logs_folder": str(tmp_path / "logs"),
        "state_file": str(tmp_path / "state.json"),
        "log_level": "ERROR",
        "discovery": {
            "use_overpass": False,
            "overpass_url": "https://overpass-api.de/api/interpreter",
            "overpass_timeout": 30,
            "use_nominatim": False,
            "nominatim_url": "https://nominatim.openstreetmap.org",
            "amenity_tags": ["restaurant", "cafe"],
            "cuisine_nodes": True,
        },
        "user_agents": ["RestaurantCrawler-Test/1.0"],
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    return build_settings(config_path)


@pytest.fixture()
def repo(settings: Settings) -> RestaurantRepository:
    db = Database(settings.db_path)
    return RestaurantRepository(db)


SAMPLE_MENU_HTML = """
<html><body>
  <h2>Entradas</h2>
  <div class="menu-item">
    <h4 class="name">Bolinho de Bacalhau</h4>
    <p class="description">Com molho tártaro</p>
    <span class="price">R$ 28,90</span>
  </div>
  <div class="menu-item">
    <h4 class="name">Carne de Sol</h4>
    <span class="price">R$ 65,00</span>
  </div>
  <h2>Bebidas</h2>
  <div class="menu-item">
    <h4 class="name">Suco de Caju</h4>
    <span class="price">R$ 12,00</span>
  </div>
</body></html>
"""
