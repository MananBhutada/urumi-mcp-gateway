import asyncio
import importlib.util
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services/woo-mcp"))

from app.tools import orders, products
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


def _registered_tools():
    registered = {}

    class Registry:
        def tool(self):
            def register(function):
                registered[function.__name__] = function
                return function
            return register

    registry = Registry()
    products.register(registry)
    orders.register(registry)
    return registered


def test_woocommerce_mcp_registers_required_and_legacy_tool_names():
    tools = _registered_tools()

    assert {
        "get_products", "get_orders", "create_order", "get_customer",
        "list_products", "create_product", "list_orders", "get_order",
        "update_order_status",
    } <= set(tools)


def test_required_tools_are_exposed_with_expected_mcp_arguments():
    from app.server import mcp

    tools = {tool.name: tool for tool in mcp._tool_manager.list_tools()}
    assert {"get_products", "get_orders", "get_customer", "create_order"} <= set(tools)
    assert tools["get_customer"].parameters["required"] == ["customer_id"]
    assert set(tools["create_order"].parameters["required"]) == {
        "product_id", "quantity", "test_order",
    }
    assert tools["create_order"].parameters["properties"]["test_order"]["type"] == "boolean"


def test_get_products_and_get_orders_use_safe_projections(monkeypatch):
    calls = []

    async def fake_request(method, path, params=None, json=None):
        calls.append((method, path, params, json))
        if path == "/products":
            return [{"id": 1, "name": "Test", "price": "3.00", "secret": "hidden"}]
        return [{
            "id": 2, "status": "pending", "total": "3.00", "currency": "INR",
            "date_created": "2026-10-19T00:00:00", "billing": {"email": "private@example.invalid"},
            "line_items": [{"name": "Test", "quantity": 1}], "secret": "hidden",
        }]

    monkeypatch.setattr(products, "request", fake_request)
    monkeypatch.setattr(orders, "request", fake_request)
    tools = _registered_tools()

    result_products = asyncio.run(tools["get_products"](per_page=200, search=" Test "))
    result_orders = asyncio.run(tools["get_orders"](status="pending", per_page=10))

    assert calls[0] == ("GET", "/products", {"per_page": 100, "search": "Test"}, None)
    assert calls[1] == ("GET", "/orders", {"per_page": 10, "status": "pending"}, None)
    assert result_products == [{"id": 1, "name": "Test", "price": "3.00", "status": None,
                                "stock_status": None, "permalink": None}]
    assert result_orders[0]["id"] == 2
    assert "secret" not in result_orders[0]
    assert "private@example.invalid" not in str(result_orders)


def test_get_customer_returns_minimal_contact_projection(monkeypatch):
    calls = []

    async def fake_request(method, path, params=None, json=None):
        calls.append((method, path))
        return {
            "id": 7, "email": "customer@example.invalid", "first_name": "Test",
            "last_name": "Customer", "billing": {
                "phone": "5550100", "city": "Pune", "country": "IN",
                "address_1": "private address", "postcode": "123456",
            }, "shipping": {"address_1": "another private address"},
        }

    monkeypatch.setattr(orders, "request", fake_request)
    customer = asyncio.run(_registered_tools()["get_customer"](customer_id=7))

    assert calls == [("GET", "/customers/7")]
    assert customer == {
        "id": 7, "email": "customer@example.invalid", "first_name": "Test",
        "last_name": "Customer", "phone": "5550100", "city": "Pune", "country": "IN",
    }


def test_create_order_creates_only_marked_unpaid_pending_test_order(monkeypatch):
    calls = []

    async def fake_request(method, path, params=None, json=None):
        calls.append((method, path, params, json))
        return {
            "id": 41, "status": "pending", "total": "3.00", "currency": "INR",
            "date_created": "2026-10-19T00:00:00", "date_paid": None, "date_paid_gmt": None,
            "meta_data": [{"key": "_urumi_test_order", "value": "true"}],
            "line_items": [{"name": "Test", "quantity": 1}],
        }

    monkeypatch.setattr(orders, "request", fake_request)
    result = asyncio.run(_registered_tools()["create_order"](product_id=1, quantity=1, test_order=True))

    assert calls == [("POST", "/orders", None, {
        "status": "pending",
        "payment_method": "cod",
        "payment_method_title": "Urumi Test Order (Unpaid)",
        "set_paid": False,
        "line_items": [{"product_id": 1, "quantity": 1}],
        "meta_data": [{"key": "_urumi_test_order", "value": "true"}],
    })]
    assert result["id"] == 41
    assert result["test_order"] is True


@pytest.mark.parametrize(
    "response",
    [
        None,
        {"status": "processing", "meta_data": [{"key": "_urumi_test_order", "value": "true"}]},
        {"status": "pending", "date_paid": "2026-10-19T00:00:00", "meta_data": [{"key": "_urumi_test_order", "value": "true"}]},
        {"status": "pending", "meta_data": []},
        {"status": "pending", "meta_data": [{"key": "_urumi_test_order", "value": "false"}]},
    ],
)
def test_create_order_does_not_report_unconfirmed_or_paid_result_as_test(monkeypatch, response):
    async def fake_request(*args, **kwargs):
        return response

    monkeypatch.setattr(orders, "request", fake_request)
    with pytest.raises(woocommerce.WooError, match="inspect the store before retrying"):
        asyncio.run(_registered_tools()["create_order"](
            product_id=1, quantity=1, test_order=True,
        ))


@pytest.mark.parametrize(
    "arguments",
    [
        {"product_id": 1, "quantity": 1, "test_order": False},
        {"product_id": 1, "quantity": 1, "test_order": "true"},
        {"product_id": 0, "quantity": 1, "test_order": True},
        {"product_id": 1, "quantity": 21, "test_order": True},
        {"product_id": 1.5, "quantity": 1, "test_order": True},
    ],
)
def test_create_order_rejects_non_test_or_invalid_order_data(monkeypatch, arguments):
    async def unexpected_request(*args, **kwargs):
        raise AssertionError("invalid orders must not reach WooCommerce")

    monkeypatch.setattr(orders, "request", unexpected_request)
    with pytest.raises(ValueError):
        asyncio.run(_registered_tools()["create_order"](**arguments))


@pytest.mark.parametrize("customer_id", [0, -1, True, 1.5, "not-an-id"])
def test_get_customer_rejects_invalid_id_before_request(monkeypatch, customer_id):
    async def unexpected_request(*args, **kwargs):
        raise AssertionError("invalid customer ids must not reach WooCommerce")

    monkeypatch.setattr(orders, "request", unexpected_request)
    with pytest.raises(ValueError):
        asyncio.run(_registered_tools()["get_customer"](customer_id=customer_id))


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


def test_oauth_base_url_uses_host_header_for_signature(monkeypatch):
    monkeypatch.setattr(woocommerce, "BASE", "http://wordpress")
    monkeypatch.setattr(woocommerce, "HOST", "store.urumi.local")

    assert woocommerce._oauth_base_url("/products") == "http://store.urumi.local/wp-json/wc/v3/products"


def test_woo_request_uses_oauth_without_exposing_consumer_secret(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return []

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def request(self, method, url, **kwargs):
            captured.update({"method": method, "url": url, **kwargs})
            return FakeResponse()

    monkeypatch.setattr(woocommerce, "BASE", "http://wordpress")
    monkeypatch.setattr(woocommerce, "HOST", "store.urumi.local")
    monkeypatch.setattr(woocommerce, "CK", "ck_test")
    monkeypatch.setattr(woocommerce, "CS", "cs_test")
    monkeypatch.setattr(woocommerce, "TIMEOUT", 15)
    monkeypatch.setattr(woocommerce.secrets, "token_hex", lambda _: "nonce")
    monkeypatch.setattr(woocommerce.time, "time", lambda: 1234567890)
    monkeypatch.setattr(woocommerce.httpx, "AsyncClient", lambda **kwargs: FakeClient())

    assert asyncio.run(woocommerce.request("GET", "/products", {"per_page": 1})) == []
    assert captured["url"] == "http://wordpress/wp-json/wc/v3/products"
    assert captured["headers"] == {"Host": "store.urumi.local"}
    assert captured["params"]["oauth_consumer_key"] == "ck_test"
    assert captured["params"]["oauth_nonce"] == "nonce"
    assert captured["params"]["oauth_signature_method"] == "HMAC-SHA256"
    assert captured["params"]["oauth_timestamp"] == "1234567890"
    assert "oauth_signature" in captured["params"]
    assert "consumer_secret" not in captured["params"]
    assert "cs_test" not in str(captured)


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


def test_live_smoke_script_signs_requests_without_url_secret(monkeypatch):
    path = Path(__file__).resolve().parents[2] / "scripts/smoke_test_woocommerce.py"
    spec = importlib.util.spec_from_file_location("woo_smoke", path)
    smoke = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(smoke)
    monkeypatch.setattr(smoke, "BASE", "https://store.example.invalid")
    monkeypatch.setattr(smoke, "CK", "ck_test_only")
    monkeypatch.setattr(smoke, "CS", "cs_secret_must_not_be_in_url")
    monkeypatch.setattr(smoke.secrets, "token_hex", lambda _: "fixed_nonce")
    monkeypatch.setattr(smoke.time, "time", lambda: 1234567890)
    monkeypatch.delenv("WOO_HOST_HEADER", raising=False)
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b"[]"

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        return FakeResponse()

    monkeypatch.setattr(smoke.urllib.request, "urlopen", fake_urlopen)

    assert smoke.call("GET", "/products", query={"per_page": 1}) == []
    assert "oauth_signature=" in captured["url"]
    assert "oauth_consumer_key=ck_test_only" in captured["url"]
    assert "cs_secret_must_not_be_in_url" not in captured["url"]
    assert "consumer_secret" not in captured["url"]
