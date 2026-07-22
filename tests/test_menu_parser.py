"""Menu parser unit tests."""

from tests.conftest import SAMPLE_MENU_HTML
from restaurant_crawler.menus.html_menu import HtmlMenuExtractor
from restaurant_crawler.menus.price import parse_price


def test_parse_price_brl():
    price, currency = parse_price("R$ 32,50")
    assert price == 32.5
    assert currency == "BRL"
    price2, _ = parse_price("1.250,00")
    assert price2 == 1250.0


def test_html_menu_extractor():
    items = HtmlMenuExtractor().extract(SAMPLE_MENU_HTML)
    assert len(items) == 3
    names = {i.name for i in items}
    assert "Bolinho de Bacalhau" in names
    assert "Suco de Caju" in names
    bolinho = next(i for i in items if i.name == "Bolinho de Bacalhau")
    assert bolinho.category == "Entradas"
    assert bolinho.price == 28.9
