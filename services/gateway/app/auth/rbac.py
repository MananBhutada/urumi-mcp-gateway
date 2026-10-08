from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session
from ..db.session import get_db
from ..models.tables import ApiKey, User, ToolPermission
from .api_keys import hash_key

def user_from_token(db: Session, token: str | None) -> User:
    if not token:
        raise HTTPException(401, "missing bearer token")
    k = db.query(ApiKey).filter_by(key_hash=hash_key(token)).first()
    if not k or k.revoked:
        raise HTTPException(401, "invalid or revoked API key")
    u = db.get(User, k.user_id)
    if not u:
        raise HTTPException(401, "unknown user")
    return u

def current_user(authorization: str | None = Header(None), db: Session = Depends(get_db)) -> User:
    token = authorization[7:].strip() if authorization and authorization.lower().startswith("bearer ") else None
    return user_from_token(db, token)

def require_admin(u: User = Depends(current_user)) -> User:
    if u.role != "ADMIN":
        raise HTTPException(403, "admin only")
    return u

def tool_allowed(db: Session, role: str, tool: str) -> bool:
    if role == "ADMIN":
        return True
    p = db.query(ToolPermission).filter_by(role=role, tool=tool).first()
    return True if p is None else p.allowed
