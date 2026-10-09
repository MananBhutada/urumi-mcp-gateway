from decimal import Decimal, InvalidOperation

from ..woocommerce import request


def _p(p):
    return {"id": p["id"], "name": p["name"], "price": p.get("price"), "status": p.get("status"),
            "stock_status": p.get("stock_status"), "permalink": p.get("permalink")}


def validate_product(name: str, regular_price: str, status: str) -> tuple[str, str, str]:
    """Validate user-controlled product fields before calling the store API."""
    clean_name = name.strip() if isinstance(name, str) else ""
    if not clean_name:
        raise ValueError("name must not be empty")
    if len(clean_name) > 200:
        raise ValueError("name must be 200 characters or fewer")
    try:
        price = Decimal(str(regular_price))
    except (InvalidOperation, ValueError):
        raise ValueError("regular_price must be a valid non-negative decimal")
    if not price.is_finite() or price < 0:
        raise ValueError("regular_price must be a valid non-negative decimal")
    if price.as_tuple().exponent < -2:
        raise ValueError("regular_price supports at most 2 decimal places")
    clean_status = status.strip().lower() if isinstance(status, str) else ""
    if clean_status not in {"draft", "pending", "private", "publish"}:
        raise ValueError("status must be one of draft, pending, private, publish")
    return clean_name, format(price, ".2f"), clean_status


def register(mcp):
    @mcp.tool()
    async def list_products(per_page: int = 20, search: str = "") -> list[dict]:
        """List products in the WooCommerce store."""
        params = {"per_page": max(1, min(per_page, 100))}
        if search and search.strip():
            params["search"] = search.strip()[:100]
        return [_p(p) for p in await request("GET", "/products", params)]

    @mcp.tool()
    async def create_product(name: str, regular_price: str, description: str = "", status: str = "draft") -> dict:
        """Create a simple product. New products default to draft; use status='publish' to make it visible in the storefront."""
        name, regular_price, status = validate_product(name, regular_price, status)
        body = {"name": name, "type": "simple", "regular_price": regular_price,
                "description": str(description)[:10000], "status": status}
        return _p(await request("POST", "/products", json=body))
