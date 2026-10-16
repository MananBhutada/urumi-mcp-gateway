# System design notes
Tables: users, api_keys, mcp_servers, mcp_tool_cache, tool_permissions,
invitations, and audit_logs (see `services/gateway/app/models/tables.py`).

Trade-offs: synchronous SQLAlchemy is used in async handlers; the MCP endpoint
returns stateless JSON responses and does not implement an SSE session; the
tool catalog cache is stored in the configured database so gateway replicas
share the last successful catalog. The project has no Alembic migration
workflow, so schema evolution beyond additive table creation needs a planned
migration process.
