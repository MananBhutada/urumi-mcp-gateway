# System design notes
Tables: users, api_keys, mcp_servers, tool_permissions, audit_logs (see services/gateway/app/models/tables.py).
Trade-offs: sync SQLAlchemy in async handlers (simple, adequate for demo); stateless MCP responses (no SSE); tool cache in memory per replica
(each replica refreshes independently — fine for 2 replicas, revisit with Redis/pubsub at scale).
