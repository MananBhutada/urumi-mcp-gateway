import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from .config import *
from .db.session import Base, engine, SessionLocal
from .models.tables import User, ApiKey, McpServer
from .auth.api_keys import hash_key, encrypt
from .routing import router as R
from .mcp.server import api as mcp_api
from .api.admin import api as admin_api
from .api.chat import api as chat_api

def bootstrap():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if BOOTSTRAP_ADMIN_KEY and not db.query(User).filter_by(email=BOOTSTRAP_ADMIN_EMAIL).first():
            u = User(email=BOOTSTRAP_ADMIN_EMAIL, name="Admin", role="ADMIN"); db.add(u); db.flush()
            db.add(ApiKey(user_id=u.id, key_hash=hash_key(BOOTSTRAP_ADMIN_KEY), key_prefix=BOOTSTRAP_ADMIN_KEY[:14]))
        for s in SEED_SERVERS:
            if not db.query(McpServer).filter_by(name=s["name"]).first():
                db.add(McpServer(name=s["name"], url=s["url"], credential_encrypted=encrypt(s.get("credential") or os.getenv(s.get("credential_env", ""), ""))))
        db.commit()

@asynccontextmanager
async def lifespan(app):
    bootstrap()
    task = asyncio.create_task(R.health_loop(HEALTH_INTERVAL))
    yield
    task.cancel()

app = FastAPI(title="Urumi MCP Gateway", lifespan=lifespan)
app.include_router(mcp_api); app.include_router(admin_api); app.include_router(chat_api)

@app.get("/healthz")
def healthz(): return {"ok": True}
