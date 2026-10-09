from ..woocommerce import request


ALLOWED_ORDER_STATUSES = {"pending", "processing", "on-hold", "completed", "cancelled", "refunded", "failed"}


def validate_order_id(order_id: int) -> int:
    try:
        value = int(order_id)
    except (TypeError, ValueError):
        raise ValueError("order_id must be a positive integer")
    if value <= 0:
        raise ValueError("order_id must be a positive integer")
    return value


def _o(o):
    billing = o.get("billing") or {}
    return {"id": o["id"], "status": o["status"], "total": o["total"], "currency": o["currency"],
            "date_created": o["date_created"], "payment_method": o.get("payment_method_title"),
            "customer": f'{billing.get("first_name", "")} {billing.get("last_name", "")}'.strip(),
            "items": [{"name": i.get("name", ""), "quantity": i.get("quantity", 0)}
                      for i in o.get("line_items", [])]}


def register(mcp):
    @mcp.tool()
    async def list_orders(after: str = "", status: str = "any", per_page: int = 20) -> list[dict]:
        """List orders. The after parameter is an ISO8601 datetime; customer details are minimized."""
        params = {"per_page": max(1, min(per_page, 100)), "status": status}
        if after and after.strip():
            params["after"] = after.strip()[:40]
        return [_o(o) for o in await request("GET", "/orders", params)]

    @mcp.tool()
    async def get_order(order_id: int) -> dict:
        """Get one order by positive numeric id."""
        return _o(await request("GET", f"/orders/{validate_order_id(order_id)}"))

    @mcp.tool()
    async def update_order_status(order_id: int, status: str) -> dict:
        """Update an order status to a supported WooCommerce status."""
        order_id = validate_order_id(order_id)
        if not isinstance(status, str) or status not in ALLOWED_ORDER_STATUSES:
            raise ValueError(f"status must be one of {sorted(ALLOWED_ORDER_STATUSES)}")
        return _o(await request("PUT", f"/orders/{order_id}", json={"status": status}))
