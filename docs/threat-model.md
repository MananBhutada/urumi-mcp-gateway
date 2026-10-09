# Threat model

| Threat | Current control | Residual risk / follow-up |
|---|---|---|
| Stolen DB leaks user API keys | HMAC-SHA256 hashes stored; raw key shown once | Rotate the gateway secret carefully; add key expiry and rate limits |
| Upstream credential exposure | Fernet-encrypted at rest; credential write-only in admin API | Rotate encryption secret and upstream credentials operationally |
| Member escalates to admin operations | Admin dependencies protect mutation endpoints | Add automated endpoint-by-endpoint authorization tests |
| Member calls a hidden tool directly | Permission checked in execution path as well as tool listing | Unconfigured role/tool pairs currently default-allow; configure explicit denials and consider default-deny after migration/UX support |
| SSRF through upstream registration or a modified DB row | URL validation runs on registration, health refresh and before tool calls; non-HTTP(S), embedded URL credentials, metadata hostnames and selected unsafe IP ranges are rejected | Private service DNS is intentionally allowed in-cluster; hostname allowlisting and DNS-rebinding-resistant egress enforcement remain necessary for hostile/multi-tenant admin scenarios |
| Lateral movement in Kubernetes | NetworkPolicies, non-root workload settings, no public Service for MCP/DB | Must verify rendered policies and live traffic on a real cluster |
| Slow or unavailable upstream | Connection/call timeouts, per-call sessions, failures isolated by upstream | Add rate limits, circuit breakers and concurrency caps |
| Revoked key reuse | Key validity checked on every request | Verify with an external MCP client, not only local SDK tests |
| Prompt injection through tool results | Chat tools route through gateway | Tool output remains untrusted; test prompt injection and add confirmation for destructive tools |

Production configuration now fails startup unless a sufficiently long unique gateway secret and admin key are supplied and PostgreSQL is configured. Shared chart defaults no longer contain reusable credentials; disposable development values are separated into values-local.yaml. These changes still require local Helm rendering and deployment tests.
