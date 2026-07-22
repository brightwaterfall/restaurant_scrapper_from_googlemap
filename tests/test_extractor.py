"""Website extractor integration-style tests."""

from restaurant_crawler.extractors.website_extractor import WebsiteExtractor
from restaurant_crawler.models.restaurant import Restaurant


HTML = """
<html>
<head>
  <title>Sabor Nordestino</title>
  <meta property="og:image" content="https://cdn.example.com/hero.jpg"/>
</head>
<body>
  <a href="mailto:contato@sabornordestino.com.br">Email</a>
  <a href="tel:+558399998877">Telefone</a>
  <a href="https://www.instagram.com/sabornordestino">IG</a>
  <a href="https://www.ifood.com.br/delivery/joao-pessoa-pb/sabor">iFood</a>
  <a href="/cardapio">Cardápio</a>
  <address>Rua Exemplar, 50, João Pessoa - PB</address>
  <div class="horario">Segunda: 11:00-22:00</div>
</body>
</html>
"""


def test_website_extractor_fields():
    extract = WebsiteExtractor().extract(HTML, "https://sabornordestino.com.br")
    assert extract.emails
    assert extract.phones
    assert extract.instagram
    assert "iFood" in extract.delivery_platforms
    assert extract.menu_links
    assert extract.image_urls
    restaurant = Restaurant(name="Sabor Nordestino")
    WebsiteExtractor().apply_to_restaurant(restaurant, extract)
    assert restaurant.email
    assert restaurant.phone
    assert restaurant.address
