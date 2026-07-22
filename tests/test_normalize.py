"""Unit tests for normalization helpers."""

from restaurant_crawler.utils.normalize import (
    make_fingerprint,
    normalize_address,
    normalize_name,
    normalize_phone,
)


def test_normalize_name_strips_accents_and_suffixes():
    assert normalize_name("Restaurante Sabor & Arte Ltda") == "restaurante sabor arte"


def test_normalize_address_expands_abbreviations():
    result = normalize_address("Av. Epitácio Pessoa, 1000, João Pessoa - PB")
    assert result is not None
    assert "avenida" in result
    assert "joao pessoa" in result


def test_normalize_phone():
    assert normalize_phone("(83) 99999-1234") == "83999991234"
    assert normalize_phone("123") is None


def test_fingerprint_stable():
    a = make_fingerprint("Cafe Central", "Rua A, 1", -7.12, -34.84, "https://www.cafe.com", "8399999")
    b = make_fingerprint("Café Central", "Rua A, 1", -7.12, -34.84, "http://cafe.com/", "(83) 99999")
    assert a == b
