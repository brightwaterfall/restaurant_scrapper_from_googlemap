"""Tests for web enrichment classification helpers."""

from restaurant_crawler.crawler.enrichment import RestaurantEnricher
from restaurant_crawler.crawler.web_search import classify_url, ensure_http_url
from restaurant_crawler.models.restaurant import Restaurant


def test_classify_url_kinds():
    assert classify_url("https://www.instagram.com/foo") == "instagram"
    assert classify_url("https://facebook.com/bar") == "facebook"
    assert classify_url("https://www.ifood.com.br/delivery/joao-pessoa-pb/x") == "delivery"
    assert classify_url("https://www.meurestaurante.com.br/cardapio") == "website"


def test_ensure_http_url():
    assert ensure_http_url("santafarra.com.br") == "https://santafarra.com.br"
    assert ensure_http_url("https://ok.com") == "https://ok.com"
    assert ensure_http_url("") is None


def test_reclassify_instagram_as_website(settings):
    restaurant = Restaurant(
        name="Jun Sakamoto",
        website="https://instagram.com/junsakamotobrasil",
    )
    # Use enricher's static helper via a lightweight instance path
    RestaurantEnricher._reclassify_misplaced_website(restaurant)
    assert restaurant.website is None
    assert restaurant.instagram == "https://instagram.com/junsakamotobrasil"


def test_needs_enrichment(settings):
    from restaurant_crawler.utils.http_client import HttpClient

    # Construct without entering async context — only needs settings
    class _DummyHttp:
        pass

    enricher = RestaurantEnricher(settings, _DummyHttp())  # type: ignore[arg-type]
    incomplete = Restaurant(name="X", address="Rua 1")
    assert enricher.needs_enrichment(incomplete) is True
    complete = Restaurant(
        name="Y",
        website="https://y.com",
        phone="83999999999",
        facebook="https://facebook.com/y",
        instagram="https://instagram.com/y",
        delivery_platforms=["iFood"],
    )
    assert enricher.needs_enrichment(complete) is False
