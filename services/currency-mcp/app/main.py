import os, httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("currency", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
API = "https://api.frankfurter.app"

@mcp.tool()
async def convert_currency(amount: float, from_currency: str, to_currency: str) -> dict:
    """Convert an amount between currencies (ISO codes, e.g. USD, INR)."""
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"{API}/latest", params={"amount": amount, "from": from_currency.upper(), "to": to_currency.upper()})
    r.raise_for_status()
    return r.json()

@mcp.tool()
async def list_rates(base: str = "USD") -> dict:
    """Latest exchange rates for a base currency."""
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"{API}/latest", params={"from": base.upper()})
    r.raise_for_status()
    return r.json()

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
