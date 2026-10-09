import re
import secrets
import time
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..db.session import get_db
from ..models.tables import User, ApiKey, Invitation, McpServer, AuditLog, ToolPermission
from ..auth.rbac import current_user, require_admin
from ..auth.api_keys import generate_key, hash_key, encrypt
from ..routing import router as R

api = APIRouter(prefix="/api")


# ---- identity
@api.get("/me")
def me(u: User = Depends(current_user)):
    return {"id": u.id, "email": u.email, "name": u.name, "role": u.role}


# ---- servers (credential is write-only)
class ServerIn(BaseModel):
    name: str
    url: str
    credential: str = ""
    enabled: bool = True


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


# ---- users, keys, and one-time invitations
class UserIn(BaseModel):
    email: str
    name: str = ""
    role: str = "MEMBER"


class InviteIn(BaseModel):
    email: str
    role: str = "MEMBER"


class AcceptInviteIn(BaseModel):
    token: str
    name: str = ""


def _normalize_email(value: str) -> str:
    email = value.strip().lower()
    if len(email) > 255 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(400, "a valid email address is required")
    return email


@api.get("/users")
def users(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return [{"id": u.id, "email": u.email, "name": u.name, "role": u.role,
             "keys": [{"id": k.id, "prefix": k.key_prefix, "revoked": k.revoked} for k in db.query(ApiKey).filter_by(user_id=u.id)]}
            for u in db.query(User)]


@api.post("/users")
def add_user(b: UserIn, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    if b.role not in ("ADMIN", "MEMBER"): raise HTTPException(400, "role must be ADMIN or MEMBER")
    email = _normalize_email(b.email)
    if db.query(User).filter_by(email=email).first(): raise HTTPException(409, "user already exists")
    u = User(email=email, name=b.name.strip(), role=b.role); db.add(u); db.commit(); return {"id": u.id}


@api.post("/invitations")
def create_invitation(b: InviteIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    email = _normalize_email(b.email)
    if b.role not in ("ADMIN", "MEMBER"):
        raise HTTPException(400, "role must be ADMIN or MEMBER")
    if db.query(User).filter_by(email=email).first():
        raise HTTPException(409, "user already exists")
    now = int(time.time())
    # Invalidate any outstanding invite for this email before issuing a replacement.
    for old in db.query(Invitation).filter_by(email=email, accepted_at=None).all():
        old.accepted_at = now
    raw = secrets.token_urlsafe(32)
    inv = Invitation(email=email, role=b.role, token_hash=hash_key(raw),
                     expires_at=now + 7 * 24 * 60 * 60, created_by_user_id=admin.id)
    db.add(inv); db.commit()
    return {"email": email, "role": b.role, "invite_token": raw,
            "expires_at": inv.expires_at, "note": "copy this token into the invitation link; shown once"}


@api.post("/invitations/accept")
def accept_invitation(b: AcceptInviteIn, db: Session = Depends(get_db)):
    if not b.token or len(b.token) > 256:
        raise HTTPException(400, "invalid invitation token")
    inv = db.query(Invitation).filter_by(token_hash=hash_key(b.token)).first()
    now = int(time.time())
    if not inv or inv.accepted_at is not None or inv.expires_at <= now:
        raise HTTPException(400, "invitation is invalid, expired, or already used")
    if db.query(User).filter_by(email=inv.email).first():
        raise HTTPException(409, "an account already exists for this invitation")
    raw_key, key_hash, prefix = generate_key()
    user = User(email=inv.email, name=b.name.strip(), role=inv.role)
    db.add(user); db.flush()
    db.add(ApiKey(user_id=user.id, key_hash=key_hash, key_prefix=prefix))
    inv.accepted_at = now
    db.commit()
    return {"user": {"id": user.id, "email": user.email, "name": user.name, "role": user.role},
            "api_key": raw_key, "note": "API key shown once; save it now"}


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
    role: str = "MEMBER"
    tool: str
    allowed: bool


@api.get("/permissions")
def perms(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return [{"role": p.role, "tool": p.tool, "allowed": p.allowed} for p in db.query(ToolPermission)]


@api.put("/permissions")
def set_perm(b: PermIn, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    if b.role not in ("ADMIN", "MEMBER"):
        raise HTTPException(400, "role must be ADMIN or MEMBER")
    p = db.query(ToolPermission).filter_by(role=b.role, tool=b.tool).first()
    if p: p.allowed = b.allowed
    else: db.add(ToolPermission(role=b.role, tool=b.tool, allowed=b.allowed))
    db.commit(); return {"ok": True}


# ---- audit
@api.get("/audit")
def audit(limit: int = 100, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    rows = db.query(AuditLog).order_by(AuditLog.id.desc()).limit(min(max(limit, 1), 500))
    return [{"id": a.id, "user": a.user_email, "server": a.server_name, "tool": a.tool_name, "source": a.source,
             "started_at": a.started_at.isoformat(), "duration_ms": a.duration_ms, "success": a.success, "error": a.error} for a in rows]
