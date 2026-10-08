from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..db.session import get_db
from ..models.tables import User, ApiKey, McpServer, AuditLog, ToolPermission
from ..auth.rbac import current_user, require_admin
from ..auth.api_keys import generate_key, encrypt
from ..routing import router as R

api = APIRouter(prefix="/api")

# ---- identity
@api.get("/me")
def me(u: User = Depends(current_user)):
    return {"id": u.id, "email": u.email, "name": u.name, "role": u.role}

# ---- servers (credential is write-only)
class ServerIn(BaseModel):
    name: str; url: str; credential: str = ""; enabled: bool = True

def _srv(s: McpServer):
    return {"id": s.id, "name": s.name, "url": s.url, "enabled": s.enabled, "status": s.status,
            "last_error": s.last_error, "tool_count": len(R.TOOL_CACHE.get(s.name, [])), "has_credential": bool(s.credential_encrypted)}

@api.get("/servers")
def servers(db: Session = Depends(get_db), u: User = Depends(current_user)):
    return [_srv(s) for s in db.query(McpServer).order_by(McpServer.id)]

@api.post("/servers")
async def add_server(b: ServerIn, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    try: R.validate_url(b.url)
    except ValueError as e: raise HTTPException(400, str(e))
    if not b.name.replace("-", "").replace("_", "").isalnum() or "__" in b.name:
        raise HTTPException(400, "name must be alphanumeric/-/_ and not contain '__'")
    s = McpServer(name=b.name.lower(), url=b.url, credential_encrypted=encrypt(b.credential), enabled=b.enabled)
    db.add(s); db.commit(); await R.refresh_server(s.id); db.refresh(s); return _srv(s)

@api.patch("/servers/{sid}")
async def patch_server(sid: int, b: dict, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    s = db.get(McpServer, sid)
    if not s: raise HTTPException(404)
    if "url" in b:
        try: R.validate_url(b["url"])
        except ValueError as e: raise HTTPException(400, str(e))
        s.url = b["url"]
    if "enabled" in b: s.enabled = bool(b["enabled"])
    if b.get("credential"): s.credential_encrypted = encrypt(b["credential"])
    db.commit(); await R.refresh_server(s.id); db.refresh(s); return _srv(s)

@api.delete("/servers/{sid}")
def del_server(sid: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    s = db.get(McpServer, sid)
    if s: R.TOOL_CACHE.pop(s.name, None); db.delete(s); db.commit()
    return {"ok": True}

@api.get("/tools")
def tools(u: User = Depends(current_user)):
    return R.tools_for(u)

# ---- users & keys
class UserIn(BaseModel):
    email: str; name: str = ""; role: str = "MEMBER"

@api.get("/users")
def users(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return [{"id": u.id, "email": u.email, "name": u.name, "role": u.role,
             "keys": [{"id": k.id, "prefix": k.key_prefix, "revoked": k.revoked} for k in db.query(ApiKey).filter_by(user_id=u.id)]}
            for u in db.query(User)]

@api.post("/users")
def add_user(b: UserIn, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    if b.role not in ("ADMIN", "MEMBER"): raise HTTPException(400, "role must be ADMIN or MEMBER")
    u = User(email=b.email, name=b.name, role=b.role); db.add(u); db.commit(); return {"id": u.id}

def _mint(db, user_id):
    raw, h, pre = generate_key(); db.add(ApiKey(user_id=user_id, key_hash=h, key_prefix=pre)); db.commit()
    return {"api_key": raw, "note": "shown once; store it now"}

@api.post("/users/{uid}/keys")
def mint_for(uid: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    if not db.get(User, uid): raise HTTPException(404)
    return _mint(db, uid)

@api.post("/me/keys")
def mint_self(db: Session = Depends(get_db), u: User = Depends(current_user)):
    return _mint(db, u.id)

@api.post("/keys/{kid}/revoke")
def revoke(kid: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    k = db.get(ApiKey, kid)
    if not k: raise HTTPException(404)
    k.revoked = True; db.commit(); return {"ok": True}

# ---- tool permissions (standout)
class PermIn(BaseModel):
    role: str = "MEMBER"; tool: str; allowed: bool

@api.get("/permissions")
def perms(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return [{"role": p.role, "tool": p.tool, "allowed": p.allowed} for p in db.query(ToolPermission)]

@api.put("/permissions")
def set_perm(b: PermIn, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    p = db.query(ToolPermission).filter_by(role=b.role, tool=b.tool).first()
    if p: p.allowed = b.allowed
    else: db.add(ToolPermission(role=b.role, tool=b.tool, allowed=b.allowed))
    db.commit(); return {"ok": True}

# ---- audit
@api.get("/audit")
def audit(limit: int = 100, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    rows = db.query(AuditLog).order_by(AuditLog.id.desc()).limit(min(limit, 500))
    return [{"id": a.id, "user": a.user_email, "server": a.server_name, "tool": a.tool_name, "source": a.source,
             "started_at": a.started_at.isoformat(), "duration_ms": a.duration_ms, "success": a.success, "error": a.error} for a in rows]
