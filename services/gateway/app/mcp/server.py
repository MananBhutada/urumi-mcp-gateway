"""Gateway-as-MCP-server for external clients (Cursor, MCP Inspector, Claude).
Implements Streamable HTTP (stateless, JSON responses) over POST /mcp, authenticated per request."""
from fastapi import APIRouter, Request, Response, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from ..db.session import get_db
from ..auth.rbac import user_from_token
from ..routing import router as R

api = APIRouter()

def _err(id_, code, msg, status=200):
    return JSONResponse({"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": msg}}, status_code=status)

@api.post("/mcp")
async def mcp_endpoint(request: Request, db: Session = Depends(get_db)):
    auth = request.headers.get("authorization", "")
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else None
    try:
        user = user_from_token(db, token)
    except Exception:
        return JSONResponse({"error": "unauthorized"}, status_code=401, headers={"WWW-Authenticate": "Bearer"})
    msg = await request.json()
    method, id_, params = msg.get("method"), msg.get("id"), msg.get("params") or {}
    if id_ is None:                       # notification
        return Response(status_code=202)
    if method == "initialize":
        return JSONResponse({"jsonrpc": "2.0", "id": id_, "result": {
            "protocolVersion": params.get("protocolVersion", "2025-03-26"),
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "urumi-gateway", "version": "0.1.0"}}})
    if method == "ping":
        return JSONResponse({"jsonrpc": "2.0", "id": id_, "result": {}})
    if method == "tools/list":
        return JSONResponse({"jsonrpc": "2.0", "id": id_, "result": {"tools": R.tools_for(user)}})
    if method == "tools/call":
        res = await R.execute(user, params.get("name", ""), params.get("arguments") or {}, "mcp")
        return JSONResponse({"jsonrpc": "2.0", "id": id_, "result": res})
    return _err(id_, -32601, f"method not found: {method}")
