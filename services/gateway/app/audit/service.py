from ..db.session import SessionLocal
from ..models.tables import AuditLog

def record(user, server: str, tool: str, started, duration_ms: int, success: bool, error: str = "", source="mcp"):
    with SessionLocal() as db:
        db.add(AuditLog(user_id=user.id if user else None, user_email=user.email if user else "",
                        server_name=server, tool_name=tool, started_at=started, duration_ms=duration_ms,
                        success=success, error=error[:1000], source=source))
        db.commit()
