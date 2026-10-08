from ..woocommerce import request

def _p(p):
    return {"id": p["id"], "name": p["name"], "price": p.get("price"), "status": p.get("status"),
            "stock_status": p.get("stock_status"), "permalink": p.get("permalink")}

def register(mcp):
    @mcp.tool()
    async def list_products(per_page: int = 20, search: str = "") -> list[dict]:
        """List products in the WooCommerce store."""
        params = {"per_page": max(1, min(per_page, 100))}
        if search: params["search"] = search
        return [_p(p) for p in await request("GET", "/products", params)]

    @mcp.tool()
    async def create_product(name: str, regular_price: str, description: str = "", status: str = "publish") -> dict:
        """Create a simple product. regular_price is a string like '999'."""
        body = {"name": name, "type": "simple", "regular_price": str(regular_price),
                "description": description, "status": status}
        return _p(await request("POST", "/products", json=body))
