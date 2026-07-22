"""Website detector tests."""

from restaurant_crawler.crawler.website_detector import WebsiteDetector, WebsiteType


def test_detect_static():
    html = "<html><body><h1>Restaurante</h1><p>Cardápio delicioso com peixes.</p></body></html>"
    result = WebsiteDetector().detect(html)
    assert result.website_type == WebsiteType.STATIC


def test_detect_dynamic_spa():
    html = """
    <html><body><div id="root"></div>
    <script src="bundle.js"></script><script>window.__INITIAL_STATE__={}</script>
    </body></html>
    """
    result = WebsiteDetector().detect(html)
    assert result.website_type == WebsiteType.DYNAMIC
