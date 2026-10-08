from ..woocommerce import request

def _o(o):
    return {"id": o["id"], "status": o["status"], "total": o["total"], "currency": o["currency"],
            "date_created": o["date_created"], "payment_method": o.get("payment_method_title"),
            "customer": f'{o["billing"].get("first_name","")} {o["billing"].get("last_name","")}'.strip(),
            "items": [{"name": i["name"], "quantity": i["quantity"]} for i in o.get("line_items", [])]}

def register(mcp):
    @mcp.tool()
    async def list_orders(after: str = "", status: str = "any", per_page: int = 20) -> list[dict]:
        """List orders. `after` is an ISO8601 datetime (e.g. 2026-10-09T00:00:00) to get today's orders."""
        params = {"per_page": max(1, min(per_page, 100)), "status": status}
        if after: params["after"] = after
        return [_o(o) for o in await request("GET", "/orders", params)]

    @mcp.tool()
    async def get_order(order_id: int) -> dict:
        """Get one order by id."""
        return _o(await request("GET", f"/orders/{int(order_id)}"))

    @mcp.tool()
    async def update_order_status(order_id: int, status: str) -> dict:
        """Set order status: pending, processing, on-hold, completed, cancelled, refunded, failed."""
        allowed = {"pending", "processing", "on-hold", "completed", "cancelled", "refunded", "failed"}
        if status not in allowed:
            raise ValueError(f"status must be one of {sorted(allowed)}")
        return _o(await request("PUT", f"/orders/{int(order_id)}", json={"status": status}))
