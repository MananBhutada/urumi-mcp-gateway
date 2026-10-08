"""Local end-to-end check (no k8s): official MCP SDK client -> gateway /mcp -> upstreams.
Usage: BASE=http://localhost:8000 KEY=urumi_live_... python tests/integration/e2e_local.py"""
import asyncio, os, json, sys
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

BASE = os.getenv("BASE", "http://localhost:8000"); KEY = os.environ["KEY"]

async def main():
    async with streamablehttp_client(f"{BASE}/mcp", headers={"Authorization": f"Bearer {KEY}"}) as (r, w, _):
        async with ClientSession(r, w) as s:
            init = await s.initialize(); print("initialize ok:", init.serverInfo.name, init.protocolVersion)
            tools = (await s.list_tools()).tools; names = sorted(t.name for t in tools)
            print(f"tools/list ({len(names)}):", names)
            res = await s.call_tool("woocommerce__create_product", {"name": "Test Shirt", "regular_price": "999"})
            print("create_product isError=", res.isError, [c.text for c in res.content])
            res = await s.call_tool("woocommerce__list_orders", {"after": "2026-10-09T00:00:00"})
            print("list_orders isError=", res.isError, [c.text[:120] for c in res.content])
            res = await s.call_tool("nope__x", {}); print("unknown tool isError=", res.isError, [c.text for c in res.content])

asyncio.run(main())
