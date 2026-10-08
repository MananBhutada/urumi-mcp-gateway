import os, httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("weather", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))

async def _geo(city: str):
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get("https://geocoding-api.open-meteo.com/v1/search", params={"name": city, "count": 1})
    res = r.json().get("results")
    if not res: raise ValueError(f"unknown city: {city}")
    return res[0]

@mcp.tool()
async def get_weather(city: str) -> dict:
    """Current weather for a city."""
    g = await _geo(city)
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": g["latitude"], "longitude": g["longitude"], "current_weather": "true"})
    return {"city": g["name"], "country": g.get("country"), **r.json()["current_weather"]}

@mcp.tool()
async def get_forecast(city: str, days: int = 3) -> dict:
    """Daily max/min temperature forecast (1-7 days)."""
    g = await _geo(city)
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": g["latitude"], "longitude": g["longitude"], "forecast_days": max(1, min(days, 7)),
            "daily": "temperature_2m_max,temperature_2m_min", "timezone": "auto"})
    return {"city": g["name"], "daily": r.json()["daily"]}

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
