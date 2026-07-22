"""Validation pipeline tests."""

from restaurant_crawler.models.menu import Menu, MenuItem
from restaurant_crawler.models.restaurant import Restaurant
from restaurant_crawler.pipelines.validation_pipeline import ValidationPipeline


def test_validation_flags_missing_address(settings, repo):
    repo.upsert_restaurant(
        Restaurant(name="Sem Endereco", latitude=-7.12, longitude=-34.84)
    )
    report = ValidationPipeline(settings, repo).validate()
    assert report.total_restaurants == 1
    assert any(i.code == "missing_address" for i in report.issues)


def test_validation_success(settings, repo):
    restaurant = Restaurant(
        name="Completo",
        address="Av. Epitácio Pessoa, 100",
        latitude=-7.12,
        longitude=-34.84,
    )
    repo.upsert_restaurant(restaurant)
    menu = Menu(restaurant_id=restaurant.id, item_count=1, extracted=True)
    repo.upsert_menu(menu)
    repo.insert_menu_items(
        [
            MenuItem(
                menu_id=menu.id,
                restaurant_id=restaurant.id,
                name="Prato Feito",
                price=25.0,
            )
        ]
    )
    # photos not required by default
    report = ValidationPipeline(settings, repo).validate()
    assert report.valid_restaurants == 1
