"""Deduplication tests."""

from restaurant_crawler.models.restaurant import Restaurant
from restaurant_crawler.utils.deduplication import Deduplicator


def test_exact_fingerprint_duplicate():
    deduper = Deduplicator(threshold=90)
    a = Restaurant(name="Cantina da Praia", address="Av. Beira Mar, 10", phone="83911112222")
    deduper.register(a)
    b = Restaurant(name="Cantina da Praia", address="Av. Beira Mar, 10", phone="83911112222")
    match = deduper.find_duplicate(b)
    assert match.is_duplicate
    assert match.existing is not None
    assert match.existing.id == a.id


def test_fuzzy_name_address_duplicate():
    deduper = Deduplicator(threshold=90)
    a = Restaurant(
        name="Restaurante Maré Alta",
        address="Rua das Trincheiras, 200, João Pessoa",
        latitude=-7.12,
        longitude=-34.84,
    )
    deduper.register(a)
    b = Restaurant(
        name="Restaurante Mare Alta",
        address="Rua das Trincheiras 200 Joao Pessoa",
        latitude=-7.12001,
        longitude=-34.84001,
    )
    match = deduper.find_duplicate(b)
    assert match.is_duplicate


def test_unique_restaurants():
    deduper = Deduplicator(threshold=90)
    a = Restaurant(name="Pizzaria Roma", address="Centro")
    deduper.register(a)
    b = Restaurant(name="Sushi Nikkei", address="Manaíra")
    match = deduper.find_duplicate(b)
    assert not match.is_duplicate
