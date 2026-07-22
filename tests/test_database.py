"""Database / repository tests."""

from restaurant_crawler.models.menu import Menu, MenuItem
from restaurant_crawler.models.photo import Photo
from restaurant_crawler.models.restaurant import Restaurant
from restaurant_crawler.models.source import Source


def test_upsert_and_get_restaurant(repo):
    restaurant = Restaurant(
        name="Teste Food",
        address="Rua Teste, 1",
        latitude=-7.12,
        longitude=-34.84,
        website="https://example.com",
    )
    repo.upsert_restaurant(restaurant)
    loaded = repo.get_restaurant(restaurant.id)
    assert loaded is not None
    assert loaded.name == "Teste Food"
    assert loaded.google_maps_url


def test_menu_and_items(repo):
    restaurant = Restaurant(name="Menu House", address="Rua 2")
    repo.upsert_restaurant(restaurant)
    menu = Menu(restaurant_id=restaurant.id, title="Almoço", source_type="html", item_count=1)
    item = MenuItem(
        menu_id=menu.id,
        restaurant_id=restaurant.id,
        name="Feijoada",
        price=45.0,
        currency="BRL",
        category="Pratos",
    )
    repo.upsert_menu(menu)
    repo.insert_menu_items([item])
    assert len(repo.list_menus(restaurant.id)) == 1
    assert repo.list_menu_items(restaurant.id)[0].name == "Feijoada"


def test_photos_sources_stats(repo):
    restaurant = Restaurant(name="Foto Bar", address="Rua 3")
    repo.upsert_restaurant(restaurant)
    repo.upsert_photo(
        Photo(
            restaurant_id=restaurant.id,
            source_url="https://example.com/a.jpg",
            downloaded=True,
            filename="foto-bar_001.jpg",
        )
    )
    repo.insert_source(
        Source(
            restaurant_id=restaurant.id,
            source_type="website",
            url="https://example.com",
        )
    )
    stats = repo.stats()
    assert stats["restaurants"] == 1
    assert stats["photos_downloaded"] == 1
    assert stats["sources"] == 1
