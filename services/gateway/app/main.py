import os
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy import text
from .config import *
from .db.session import Base, engine, SessionLocal
from .models.tables import User, ApiKey, McpServer
from .auth.api_keys import hash_key, encrypt
from .routing import router as R
from .mcp.server import api as mcp_api
from .api.admin import api as admin_api
from .api.chat import api as chat_api


logger = logging.getLogger(__name__)
BOOTSTRAP_LOCK_ID = 554911230001


def _lock_bootstrap(db):
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(:lock_id)"),
            {"lock_id": BOOTSTRAP_LOCK_ID},
        )
    elif dialect != "sqlite":
        raise RuntimeError("bootstrap locking is unsupported for this database")


def bootstrap():
    validate_runtime_config()
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        _lock_bootstrap(db)
        if BOOTSTRAP_ADMIN_KEY:
            admin = db.query(User).filter_by(email=BOOTSTRAP_ADMIN_EMAIL).with_for_update().first()
            if admin is None:
                admin = User(email=BOOTSTRAP_ADMIN_EMAIL, name="Admin", role="ADMIN")
                db.add(admin)
                db.flush()
                db.add(ApiKey(
                    user_id=admin.id,
                    key_hash=hash_key(BOOTSTRAP_ADMIN_KEY),
                    key_prefix=BOOTSTRAP_ADMIN_KEY[:14],
                ))
            elif BOOTSTRAP_ADMIN_KEY_RECOVERY:
                if admin.role != "ADMIN":
                    raise RuntimeError(
                        "bootstrap key recovery requires the existing account to have the ADMIN role"
                    )
                configured_hash = hash_key(BOOTSTRAP_ADMIN_KEY)
                existing_key = db.query(ApiKey).filter_by(key_hash=configured_hash).one_or_none()
                if existing_key is None:
                    db.add(ApiKey(
                        user_id=admin.id,
                        key_hash=configured_hash,
                        key_prefix=BOOTSTRAP_ADMIN_KEY[:14],
                    ))
                    logger.warning("Bootstrap admin key recovery added a key; existing keys were preserved")
                elif existing_key.user_id != admin.id:
                    raise RuntimeError(
                        "configured bootstrap key is already assigned to a different user"
                    )
                elif existing_key.revoked:
                    raise RuntimeError(
                        "configured bootstrap key is revoked; choose a different key for explicit recovery"
                    )
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
def healthz():
    return {"ok": True}
