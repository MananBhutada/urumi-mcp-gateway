"""Gateway MCP endpoint: stateless Streamable HTTP JSON-RPC with per-request bearer auth."""
import json
from fastapi import APIRouter, Request, Response, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from ..db.session import get_db
from ..auth.rbac import user_from_token
from ..routing import router as R

api = APIRouter()
SUPPORTED_PROTOCOL_VERSIONS = {"2024-11-05", "2025-03-26", "2025-06-18"}
SERVER_PROTOCOL_VERSION = "2025-03-26"


def _err(id_, code, msg, status=200):
    return JSONResponse({"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": msg}}, status_code=status)


def _is_valid_request(msg):
    return (
        isinstance(msg, dict)
        and msg.get("jsonrpc") == "2.0"
        and isinstance(msg.get("method"), str)
        and bool(msg.get("method"))
        and ("id" not in msg or isinstance(msg.get("id"), (str, int, float, type(None))))
        and not isinstance(msg.get("id"), bool)
        and ("params" not in msg or isinstance(msg.get("params"), dict))
    )


@api.post("/mcp")
async def mcp_endpoint(request: Request, db: Session = Depends(get_db)):
    auth = request.headers.get("authorization", "")
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else None
    try:
        user = user_from_token(db, token)
    except Exception:
        return JSONResponse({"error": "unauthorized"}, status_code=401, headers={"WWW-Authenticate": "Bearer"})

    try:
        msg = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return _err(None, -32700, "Parse error")

    if not _is_valid_request(msg):
        return _err(msg.get("id") if isinstance(msg, dict) else None, -32600, "Invalid Request")

    method = msg["method"]
    id_ = msg.get("id")
    params = msg.get("params") or {}

    # MCP notifications are accepted without a JSON-RPC response.
    if "id" not in msg:
        if method in {"notifications/initialized", "notifications/cancelled", "notifications/progress", "notifications/roots/list_changed"}:
            return Response(status_code=202)
        if method.startswith("notifications/"):
            return Response(status_code=202)
        return _err(None, -32600, "Requests must include an id")

    if method == "initialize":
        requested = params.get("protocolVersion")
        version = requested if requested in SUPPORTED_PROTOCOL_VERSIONS else SERVER_PROTOCOL_VERSION
        return JSONResponse({"jsonrpc": "2.0", "id": id_, "result": {
            "protocolVersion": version,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "urumi-gateway", "version": "0.1.0"}}})
    if method in {"notifications/initialized", "notifications/cancelled", "notifications/progress", "notifications/roots/list_changed"}:
        return _err(id_, -32600, "Notification methods must not include an id")
    if method == "ping":
        return JSONResponse({"jsonrpc": "2.0", "id": id_, "result": {}})
    if method == "tools/list":
        return JSONResponse({"jsonrpc": "2.0", "id": id_, "result": {"tools": R.tools_for(user)}})
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not isinstance(name, str) or not name or not isinstance(arguments, dict):
            return _err(id_, -32602, "tools/call requires a string name and object arguments")
        res = await R.execute(user, name, arguments, "mcp")
        return JSONResponse({"jsonrpc": "2.0", "id": id_, "result": res})
    if method == "resources/list":
        return JSONResponse({"jsonrpc": "2.0", "id": id_, "result": {"resources": []}})
    if method == "prompts/list":
        return JSONResponse({"jsonrpc": "2.0", "id": id_, "result": {"prompts": []}})
    return _err(id_, -32601, f"method not found: {method}")
