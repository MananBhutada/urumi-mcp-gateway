from ..woocommerce import WooError, request


ALLOWED_ORDER_STATUSES = {"pending", "processing", "on-hold", "completed", "cancelled", "refunded", "failed"}


def validate_order_id(order_id: int) -> int:
    return _positive_id(order_id, "order_id")


def _o(o):
    billing = o.get("billing") or {}
    return {"id": o["id"], "status": o["status"], "total": o["total"], "currency": o["currency"],
            "date_created": o["date_created"], "payment_method": o.get("payment_method_title"),
            "customer": f'{billing.get("first_name", "")} {billing.get("last_name", "")}'.strip(),
            "items": [{"name": i.get("name", ""), "quantity": i.get("quantity", 0)}
                      for i in o.get("line_items", [])]}


def _customer(customer):
    billing = customer.get("billing") or {}
    return {
        "id": customer["id"],
        "email": customer.get("email", ""),
        "first_name": customer.get("first_name", ""),
        "last_name": customer.get("last_name", ""),
        "phone": billing.get("phone", ""),
        "city": billing.get("city", ""),
        "country": billing.get("country", ""),
    }


def _positive_id(value, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a positive integer")
    if isinstance(value, int):
        result = value
    elif isinstance(value, str) and value.isdecimal():
        result = int(value)
    else:
        raise ValueError(f"{field} must be a positive integer")
    if result <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return result


def _confirmed_test_order(order: dict) -> dict:
    if not isinstance(order, dict):
        raise WooError(
            "WooCommerce returned an invalid order response; "
            "inspect the store before retrying"
        )
    metadata = order.get("meta_data")
    has_test_marker = isinstance(metadata, list) and any(
        isinstance(item, dict)
        and item.get("key") == "_urumi_test_order"
        and item.get("value") == "true"
        for item in metadata
    )
    if (
        order.get("status") != "pending"
        or order.get("date_paid")
        or order.get("date_paid_gmt")
        or order.get("set_paid") is True
        or not has_test_marker
    ):
        raise WooError(
            "WooCommerce did not confirm a pending, unpaid marked test order; "
            "inspect the store before retrying"
        )
    try:
        return {**_o(order), "test_order": True}
    except (KeyError, TypeError) as exc:
        raise WooError(
            "WooCommerce returned an incomplete order response; "
            "inspect the store before retrying"
        ) from exc


def register(mcp):
    async def orders_page(after: str, status: str, per_page: int) -> list[dict]:
        params = {"per_page": max(1, min(per_page, 100)), "status": status}
        if after and after.strip():
            params["after"] = after.strip()[:40]
        return [_o(o) for o in await request("GET", "/orders", params)]

    @mcp.tool()
    async def list_orders(after: str = "", status: str = "any", per_page: int = 20) -> list[dict]:
        """List orders. The after parameter is an ISO8601 datetime; customer details are minimized."""
        return await orders_page(after, status, per_page)

    @mcp.tool()
    async def get_orders(after: str = "", status: str = "any", per_page: int = 20) -> list[dict]:
        """Get WooCommerce orders. Customer details are minimized."""
        return await orders_page(after, status, per_page)

    @mcp.tool()
    async def get_order(order_id: int) -> dict:
        """Get one order by positive numeric id."""
        return _o(await request("GET", f"/orders/{validate_order_id(order_id)}"))

    @mcp.tool()
    async def get_customer(customer_id: int) -> dict:
        """Get a customer's basic contact details by WooCommerce customer id."""
        return _customer(await request("GET", f"/customers/{_positive_id(customer_id, 'customer_id')}"))

    @mcp.tool()
    async def create_order(product_id: int, quantity: int, test_order: bool) -> dict:
        """Create an unpaid, clearly marked test order for one existing product.

        test_order must be true. This tool never accepts customer details, marks
        an order paid, or creates a processing/completed order.
        """
        product_id = _positive_id(product_id, "product_id")
        quantity = _positive_id(quantity, "quantity")
        if quantity > 20:
            raise ValueError("quantity must be 20 or fewer")
        if test_order is not True:
            raise ValueError("test_order must be true; this tool only creates test orders")
        order = await request("POST", "/orders", json={
            "status": "pending",
            "payment_method": "cod",
            "payment_method_title": "Urumi Test Order (Unpaid)",
            "set_paid": False,
            "line_items": [{"product_id": product_id, "quantity": quantity}],
            "meta_data": [{"key": "_urumi_test_order", "value": "true"}],
        })
        return _confirmed_test_order(order)

    @mcp.tool()
    async def update_order_status(order_id: int, status: str) -> dict:
        """Update an order status to a supported WooCommerce status."""
        order_id = validate_order_id(order_id)
        if not isinstance(status, str) or status not in ALLOWED_ORDER_STATUSES:
            raise ValueError(f"status must be one of {sorted(ALLOWED_ORDER_STATUSES)}")
        return _o(await request("PUT", f"/orders/{order_id}", json={"status": status}))
