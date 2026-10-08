"""Registry + routing: aggregate tools from all enabled upstreams, isolate failures,
enforce per-role tool permissions, audit every call."""
import asyncio, ipaddress, time
from datetime import datetime, timezone
from urllib.parse import urlparse
from ..config import CONNECT_TIMEOUT, CALL_TIMEOUT
from ..db.session import SessionLocal
from ..models.tables import McpServer, User
from ..auth.api_keys import decrypt
from ..auth.rbac import tool_allowed
from ..audit import service as audit
from ..mcp import client
from .collisions import namespace, split

TOOL_CACHE: dict[str, list[dict]] = {}   # server name -> raw tools (only for healthy servers)

def validate_url(url: str):
    """Basic SSRF guard: http(s) only, no cloud-metadata / link-local targets."""
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise ValueError("url must be http(s)")
    try:
        ip = ipaddress.ip_address(p.hostname)
        if ip.is_link_local or ip.is_multicast or ip.is_unspecified:
            raise ValueError("target address not allowed")
    except ValueError as e:
        if "not allowed" in str(e): raise
    if p.hostname in ("metadata.google.internal",):
        raise ValueError("target not allowed")

async def refresh_server(srv_id: int):
    with SessionLocal() as db:
        s = db.get(McpServer, srv_id)
        if not s: return
        if not s.enabled:
            s.status, s.last_error = "disabled", ""; TOOL_CACHE.pop(s.name, None); db.commit(); return
        try:
            tools = await client.list_tools(s.url, decrypt(s.credential_encrypted), CONNECT_TIMEOUT)
            TOOL_CACHE[s.name] = tools; s.status, s.last_error = "connected", ""
        except Exception as e:  # isolate: never propagate
            TOOL_CACHE.pop(s.name, None); s.status, s.last_error = "unreachable", str(e)[:300]
        db.commit()

async def refresh_all():
    with SessionLocal() as db:
        ids = [s.id for s in db.query(McpServer).all()]
    await asyncio.gather(*(refresh_server(i) for i in ids), return_exceptions=True)

async def health_loop(interval: float):
    while True:
        try: await refresh_all()
        except Exception: pass
        await asyncio.sleep(interval)

def tools_for(user: User) -> list[dict]:
    out = []
    with SessionLocal() as db:
        enabled = {s.name for s in db.query(McpServer).filter_by(enabled=True).all()}
        for server, tools in TOOL_CACHE.items():
            if server not in enabled: continue
            for t in tools:
                n = namespace(server, t["name"])
                if tool_allowed(db, user.role, n):          # hidden from tools/list if denied
                    out.append({"name": n, "description": f"[{server}] {t['description']}", "inputSchema": t["inputSchema"]})
    return out

async def execute(user: User, name: str, args: dict, source: str = "mcp") -> dict:
    started = datetime.now(timezone.utc); t0 = time.monotonic()
    server_name, tool = "", name
    def finish(ok, err=""):
        audit.record(user, server_name, tool, started, int((time.monotonic() - t0) * 1000), ok, err, source)
    try:
        server_name, tool = split(name)
        with SessionLocal() as db:
            s = db.query(McpServer).filter_by(name=server_name).first()
            if not s or not s.enabled:
                raise LookupError(f"unknown or disabled server: {server_name}")
            if not tool_allowed(db, user.role, name):       # direct invocation rejected too
                raise PermissionError(f"role {user.role} may not call {name}")
            url, cred = s.url, decrypt(s.credential_encrypted)
        res = await client.call_tool(url, cred, tool, args, CALL_TIMEOUT)
        finish(not res["isError"], "" if not res["isError"] else "tool reported error")
        return res
    except PermissionError as e:
        finish(False, str(e)); return {"content": [{"type": "text", "text": str(e)}], "isError": True}
    except Exception as e:
        finish(False, str(e)); return {"content": [{"type": "text", "text": f"gateway error: {e}"}], "isError": True}
