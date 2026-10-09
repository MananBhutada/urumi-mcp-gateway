import asyncio
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services/woo-mcp"))

from app.tools.products import validate_product
from app.tools.orders import validate_order_id, _o
from app import woocommerce


def test_product_validation_normalizes_price_and_name():
    assert validate_product("  Widget  ", "12", "DRAFT") == ("Widget", "12.00", "draft")
    assert validate_product("Widget", "12.30", "publish") == ("Widget", "12.30", "publish")


@pytest.mark.parametrize("price", ["-1", "NaN", "Infinity", "not-a-price", "1.234"])
def test_product_rejects_invalid_prices(price):
    with pytest.raises(ValueError):
        validate_product("Widget", price, "draft")


@pytest.mark.parametrize("name,status", [("", "draft"), ("   ", "draft"), ("Widget", "trash")])
def test_product_rejects_empty_name_or_unsupported_status(name, status):
    with pytest.raises(ValueError):
        validate_product(name, "1.00", status)


@pytest.mark.parametrize("value,expected", [(1, 1), ("42", 42)])
def test_order_id_accepts_positive_integer(value, expected):
    assert validate_order_id(value) == expected


@pytest.mark.parametrize("value", [0, -1, "nope", None])
def test_order_id_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        validate_order_id(value)


def test_order_projection_handles_missing_billing_without_leaking_extra_fields():
    order = {
        "id": 9, "status": "processing", "total": "12.00", "currency": "INR",
        "date_created": "2026-10-09T00:00:00", "billing": None,
        "line_items": [{"name": "Widget", "quantity": 2, "meta_data": ["private"]}],
        "secret_field": "must not be returned",
    }
    result = _o(order)
    assert result["customer"] == ""
    assert result["items"] == [{"name": "Widget", "quantity": 2}]
    assert "secret_field" not in result
    assert "meta_data" not in result["items"][0]


def test_woo_configuration_and_path_validation(monkeypatch):
    monkeypatch.setattr(woocommerce, "BASE", "http://wordpress")
    monkeypatch.setattr(woocommerce, "CK", "ck_test")
    monkeypatch.setattr(woocommerce, "CS", "cs_test")
    monkeypatch.setattr(woocommerce, "TIMEOUT", 15)
    woocommerce._validate_configuration()
    assert woocommerce._validate_path("/products/123") == "/products/123"
    for path in ("https://evil.example", "//evil.example", "/products/../orders", "/products\\x"):
        with pytest.raises(woocommerce.WooError):
            woocommerce._validate_path(path)


def test_woo_configuration_rejects_missing_credentials(monkeypatch):
    monkeypatch.setattr(woocommerce, "BASE", "http://wordpress")
    monkeypatch.setattr(woocommerce, "CK", "")
    monkeypatch.setattr(woocommerce, "CS", "cs_test")
    with pytest.raises(woocommerce.WooError, match="credentials"):
        woocommerce._validate_configuration()


def test_woo_errors_do_not_echo_upstream_response_body(monkeypatch):
    class FakeResponse:
        status_code = 500
        text = "sensitive upstream detail"
    class FakeClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return False
        async def request(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(woocommerce, "BASE", "http://wordpress")
    monkeypatch.setattr(woocommerce, "CK", "ck_test")
    monkeypatch.setattr(woocommerce, "CS", "cs_test")
    monkeypatch.setattr(woocommerce, "TIMEOUT", 15)
    monkeypatch.setattr(woocommerce.httpx, "AsyncClient", lambda **kwargs: FakeClient())

    with pytest.raises(woocommerce.WooError) as err:
        asyncio.run(woocommerce.request("GET", "/products"))
    assert "HTTP 500" in str(err.value)
    assert "sensitive upstream detail" not in str(err.value)
