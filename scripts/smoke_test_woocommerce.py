#!/usr/bin/env python3
"""Live smoke test for a deployed WooCommerce REST API.

Required environment:
  WOO_BASE_URL=https://store.example.com
  WOO_CONSUMER_KEY=ck_...
  WOO_CONSUMER_SECRET=cs_...

Optional:
  WOO_TEST_ORDER_ID=123  # test get_order endpoint against a known order
This script never prints credentials or response bodies. It creates a DRAFT product.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal
from datetime import datetime, timezone

BASE = os.environ.get("WOO_BASE_URL", "").rstrip("/")
CK = os.environ.get("WOO_CONSUMER_KEY", "")
CS = os.environ.get("WOO_CONSUMER_SECRET", "")
TIMEOUT = 15


def fail(message, code=1):
    print(f"FAIL: {message}")
    raise SystemExit(code)


def call(method, path, payload=None, query=None):
    if not BASE.startswith(("http://", "https://")) or not CK or not CS:
        fail("Set WOO_BASE_URL, WOO_CONSUMER_KEY and WOO_CONSUMER_SECRET")
    if BASE.startswith("http://") and os.environ.get("WOO_ALLOW_INSECURE_HTTP") != "1":
        fail("Refusing to send REST credentials over HTTP; use HTTPS or explicitly set WOO_ALLOW_INSECURE_HTTP=1 for a disposable local cluster")
    params = dict(query or {})
    params.update({"consumer_key": CK, "consumer_secret": CS})
    url = f"{BASE}/wp-json/wc/v3{path}?{urllib.parse.urlencode(params)}"
    body = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, method=method,
                                 headers={"Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        fail(f"{method} {path} returned HTTP {exc.code}")
    except (urllib.error.URLError, TimeoutError):
        fail(f"{method} {path} could not reach WooCommerce")
    try:
        return json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        fail(f"{method} {path} returned invalid JSON")


def main():
    print("1/4 Checking products endpoint...")
    products = call("GET", "/products", query={"per_page": 1})
    if not isinstance(products, list):
        fail("products endpoint did not return a list")
    print(f"PASS: products endpoint reachable (sample count={len(products)})")

    print("2/4 Creating a disposable DRAFT product...")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    product = call("POST", "/products", {
        "name": f"Urumi MCP Smoke Test {stamp}",
        "type": "simple",
        "regular_price": "1.00",
        "status": "draft",
        "description": "Disposable draft created by scripts/smoke_test_woocommerce.py"
    })
    product_id = product.get("id") if isinstance(product, dict) else None
    if not product_id or product.get("status") != "draft":
        fail("product creation did not return a draft product")
    fetched = call("GET", f"/products/{product_id}")
    if fetched.get("id") != product_id:
        fail("created product could not be retrieved")
    print(f"PASS: create/read draft product (id={product_id})")

    print("3/4 Checking orders endpoint...")
    orders = call("GET", "/orders", query={"per_page": 5, "status": "any"})
    if not isinstance(orders, list):
        fail("orders endpoint did not return a list")
    print(f"PASS: orders endpoint reachable (sample count={len(orders)})")

    print("4/4 Checking order lookup/status update when order ID is supplied...")
    order_id = os.environ.get("WOO_TEST_ORDER_ID")
    if not order_id:
        print("SKIP: set WOO_TEST_ORDER_ID to test order lookup and status update")
    else:
        order = call("GET", f"/orders/{int(order_id)}")
        if order.get("id") != int(order_id):
            fail("order lookup returned an unexpected order")
        print(f"PASS: order lookup (id={int(order_id)}, status={order.get('status')})")
        # This test only uses a non-destructive update to the current status. Supply an
        # order whose status is known and supported by the store's workflow.
        current_status = order.get("status")
        allowed = {"pending", "processing", "on-hold", "completed", "cancelled", "refunded", "failed"}
        if current_status not in allowed:
            fail("order has an unsupported current status; status update was not attempted")
        updated = call("PUT", f"/orders/{int(order_id)}", {"status": current_status})
        if updated.get("status") != current_status:
            fail("same-status update failed")
        print("PASS: order status update endpoint accepted a no-op status update")

    print("DONE: REST smoke checks passed. This does not prove browser checkout or Kubernetes persistence.")


if __name__ == "__main__":
    main()
