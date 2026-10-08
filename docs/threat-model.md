# Threat model (summary)
| Threat | Mitigation |
|---|---|
| Stolen DB leaks user keys | only HMAC-SHA256 hashes stored; raw shown once |
| Upstream credential exposure | Fernet-encrypted at rest; never returned by API; never sent to browser |
| Member escalates to admin ops | `require_admin` dependency on all mutating admin endpoints |
| Member calls hidden tool directly | permission check inside `execute()` (not just list filtering) |
| SSRF via "add server" URL | scheme allowlist, link-local/metadata blocked (extend with allowlist in prod) |
| Lateral movement in cluster | default-deny NetworkPolicies + explicit allows; non-root containers; no MCP/DB ingress |
| Dead/slow upstream DoS | connect+call timeouts, per-call sessions, exceptions isolated per upstream |
| Revoked key reuse | key checked on every request |
Residual: single SECRET_KEY derives HMAC+Fernet (rotate carefully); no rate limiting; no OAuth; chat prompt-injection via tool output.
