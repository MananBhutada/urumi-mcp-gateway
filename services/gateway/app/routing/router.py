"""Registry + routing: aggregate tools from all enabled upstreams, isolate failures,
enforce per-role tool permissions, audit every call."""
import asyncio, ipaddress, time
from datetime import datetime, timezone
from urllib.parse import urlparse
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from ..config import CONNECT_TIMEOUT, CALL_TIMEOUT
from ..db.session import SessionLocal
from ..models.tables import McpServer, McpToolCache, User
from ..auth.api_keys import decrypt
from ..auth.rbac import tool_allowed
from ..audit import service as audit
from ..mcp import client
from .collisions import namespace, split


def _store_tool_catalog(db, server_name: str, tools: list[dict]) -> None:
    """Upsert the shared catalog so concurrent gateway refreshes are safe."""
    dialect = db.get_bind().dialect.name
    insert = {"postgresql": postgres_insert, "sqlite": sqlite_insert}.get(dialect)
    if insert is None:
        raise RuntimeError(f"unsupported tool catalog database: {dialect}")
    statement = insert(McpToolCache).values(server_name=server_name, tools_json=tools)
    statement = statement.on_conflict_do_update(
        index_elements=[McpToolCache.server_name],
        set_={"tools_json": tools, "updated_at": datetime.now(timezone.utc)},
    )
    db.execute(statement)


def validate_url(url: str):
    """Reject malformed URLs and common SSRF targets before any upstream request.

    Private service DNS names are intentionally permitted for in-cluster MCPs.
    Production deployments should additionally restrict registered hosts with
    cluster NetworkPolicies and an operator-managed hostname allowlist.
    """
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise ValueError("url must be http(s) with a hostname")
    if p.username is not None or p.password is not None:
        raise ValueError("credentials must not be embedded in the upstream URL")
    if p.hostname.lower().rstrip(".") in {
        "metadata.google.internal", "metadata", "instance-data"
    }:
        raise ValueError("metadata target not allowed")
    try:
        ip = ipaddress.ip_address(p.hostname)
    except ValueError:
        ip = None
    if ip is not None and (
        ip.is_link_local or ip.is_multicast or ip.is_unspecified
        or ip.is_reserved
    ):
        raise ValueError("target address not allowed")


async def refresh_server(srv_id: int):
    with SessionLocal() as db:
        s = db.get(McpServer, srv_id)
        if not s: return
        if not s.enabled:
            s.status, s.last_error = "disabled", ""
            cache = db.get(McpToolCache, s.name)
            if cache: db.delete(cache)
            db.commit(); return
        try:
            # Revalidate stored URLs, not only URLs entered through the admin API.
            validate_url(s.url)
            tools = await client.list_tools(s.url, decrypt(s.credential_encrypted), CONNECT_TIMEOUT)
            _store_tool_catalog(db, s.name, tools)
            s.status, s.last_error = "connected", ""
        except Exception as e:  # isolate: never propagate across upstreams
            cache = db.get(McpToolCache, s.name)
            if cache: db.delete(cache)
            s.status, s.last_error = "unreachable", str(e)[:300]
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


def tools_for(user: User, db) -> list[dict]:
    """Build discovery from the same registry DB session used by the request."""
    out = []
    rows = (db.query(McpServer.name, McpToolCache.tools_json)
            .join(McpToolCache, McpToolCache.server_name == McpServer.name)
            .filter(McpServer.enabled.is_(True)).all())
    for server, tools in rows:
        for t in tools:
            n = namespace(server, t["name"])
            if tool_allowed(db, user.role, n):
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
            if not tool_allowed(db, user.role, name):
                raise PermissionError(f"role {user.role} may not call {name}")
            url, cred = s.url, decrypt(s.credential_encrypted)
        # Defense in depth: DB rows may predate validation or be changed outside the API.
        validate_url(url)
        res = await client.call_tool(url, cred, tool, args, CALL_TIMEOUT)
        finish(not res["isError"], "" if not res["isError"] else "tool reported error")
        return res
    except PermissionError as e:
        finish(False, str(e)); return {"content": [{"type": "text", "text": str(e)}], "isError": True}
    except Exception as e:
        finish(False, str(e)); return {"content": [{"type": "text", "text": f"gateway error: {e}"}], "isError": True}
