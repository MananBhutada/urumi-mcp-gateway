"""Upstream MCP client. Every call opens its own short-lived session with hard timeouts,
so one slow/dead upstream can never block or crash the gateway."""
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

class UpstreamError(Exception):
    def __init__(self, kind: str, msg: str):
        super().__init__(f"{kind}: {msg}"); self.kind = kind

def _root_cause(e: BaseException) -> BaseException:
    """anyio wraps connection failures in (nested) ExceptionGroups; dig out the real error."""
    while isinstance(e, BaseExceptionGroup) and e.exceptions:
        e = e.exceptions[0]
    return e

async def _run(url: str, credential: str, fn, timeout: float):
    headers = {"Authorization": f"Bearer {credential}"} if credential else None
    async def go():
        async with streamablehttp_client(url, headers=headers) as (r, w, _):
            async with ClientSession(r, w) as s:
                await s.initialize()
                return await fn(s)
    try:
        return await asyncio.wait_for(go(), timeout)
    except asyncio.TimeoutError:
        raise UpstreamError("timeout", f"no response within {timeout}s")
    except UpstreamError:
        raise
    except BaseException as e:  # includes anyio ExceptionGroup from connection failures
        if isinstance(e, (KeyboardInterrupt, SystemExit)): raise
        root = _root_cause(e)
        raise UpstreamError("connection_error", f"{type(root).__name__}: {str(root)[:200]}")

async def list_tools(url, credential, timeout):
    async def fn(s):
        res = await s.list_tools()
        return [{"name": t.name, "description": t.description or "", "inputSchema": t.inputSchema} for t in res.tools]
    return await _run(url, credential, fn, timeout)

async def call_tool(url, credential, name, args, timeout):
    async def fn(s):
        res = await s.call_tool(name, args or {})
        return {"content": [c.model_dump(exclude_none=True) for c in res.content], "isError": bool(res.isError)}
    return await _run(url, credential, fn, timeout)
