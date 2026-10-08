import hmac
import os

import uvicorn
from starlette.responses import JSONResponse

from .server import mcp


class BearerAuth:
    """Pure-ASGI bearer check. Why: NetworkPolicy alone is network-level trust; this makes
    the shared upstream credential (woo-mcp-token) a real second layer, so only the gateway can call woo-mcp."""

    def __init__(self, app, token: str):
        self.app, self.token = app, token

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            auth = dict(scope["headers"]).get(b"authorization", b"").decode()
            supplied = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
            # compare_digest: constant-time compare, avoids timing leaks of the token
            if not hmac.compare_digest(supplied.encode(), self.token.encode()):
                resp = JSONResponse({"error": "unauthorized"}, status_code=401, headers={"WWW-Authenticate": "Bearer"})
                return await resp(scope, receive, send)
        await self.app(scope, receive, send)


def build_app():
    app = mcp.streamable_http_app()  # endpoint: /mcp
    token = os.getenv("MCP_AUTH_TOKEN", "")
    if not token:
        # fail closed: refuse to start unauthenticated unless explicitly allowed (local dev only)
        if os.getenv("MCP_ALLOW_NO_AUTH") != "1":
            raise SystemExit("MCP_AUTH_TOKEN is required (set MCP_ALLOW_NO_AUTH=1 for local dev only)")
        return app
    return BearerAuth(app, token)


if __name__ == "__main__":
    uvicorn.run(build_app(), host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
