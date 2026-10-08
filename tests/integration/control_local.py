"""Local control-plane check (no k8s). Needs gateway + 3 upstreams running.
Usage: BASE=http://localhost:8000 ADMIN_KEY=... [KILL_CMD='kill ...'] python tests/integration/control_local.py"""
import os, time, subprocess, httpx
BASE = os.getenv("BASE", "http://localhost:8000"); ADMIN = os.environ["ADMIN_KEY"]
H = lambda k: {"Authorization": f"Bearer {k}", "Accept": "application/json, text/event-stream"}
def rpc(key, method, params=None, id_=1):
    return httpx.post(f"{BASE}/mcp", headers=H(key), json={"jsonrpc": "2.0", "id": id_, "method": method, "params": params or {}}, timeout=60)
def names(key): return sorted(t["name"] for t in rpc(key, "tools/list").json()["result"]["tools"])
def ok(label, cond, extra=""): print(("PASS " if cond else "FAIL ") + label, extra); return cond
res = []
a = httpx.Client(base_url=BASE, headers=H(ADMIN), timeout=30)
uid = a.post("/api/users", json={"email": f"b{int(time.time())}@urumi.local", "name": "Member B", "role": "MEMBER"}).json()["id"]
kb = a.post(f"/api/users/{uid}/keys").json()["api_key"]
res.append(ok("member B key lists tools", len(names(kb)) > 0, len(names(kb))))
res.append(ok("member cannot use admin API", httpx.get(f"{BASE}/api/users", headers=H(kb)).status_code == 403))
# permissions: deny create_product to MEMBER
a.put("/api/permissions", json={"role": "MEMBER", "tool": "woocommerce__create_product", "allowed": False})
res.append(ok("denied tool hidden from member list", "woocommerce__create_product" not in names(kb)))
r = rpc(kb, "tools/call", {"name": "woocommerce__create_product", "arguments": {"name": "x", "regular_price": "1"}}).json()["result"]
res.append(ok("denied tool rejected on direct call", r["isError"], r["content"][0]["text"]))
res.append(ok("admin still sees it", "woocommerce__create_product" in names(ADMIN)))
a.put("/api/permissions", json={"role": "MEMBER", "tool": "woocommerce__create_product", "allowed": True})
# two-upstream prompt equivalent: call weather + woo as B
r1 = rpc(kb, "tools/call", {"name": "woocommerce__list_orders", "arguments": {}}).json()["result"]
res.append(ok("member B orders call ok", not r1["isError"]))
# disable upstream
sid = next(s["id"] for s in a.get("/api/servers").json() if s["name"] == "currency")
a.patch(f"/api/servers/{sid}", json={"enabled": False})
res.append(ok("disabled upstream tools vanish", not any(n.startswith("currency__") for n in names(kb))))
a.patch(f"/api/servers/{sid}", json={"enabled": True}); time.sleep(0.5)
# revoke
kid = next(k["id"] for u in a.get("/api/users").json() if u["id"] == uid for k in u["keys"])
a.post(f"/api/keys/{kid}/revoke")
res.append(ok("revoked key -> 401", rpc(kb, "tools/list").status_code == 401))
res.append(ok("bad key -> 401", rpc("urumi_live_garbage", "tools/list").status_code == 401))
# audit
au = a.get("/api/audit?limit=50").json()
res.append(ok("audit has rows with user/server/tool/duration", len(au) > 0 and all(k in au[0] for k in ("user", "server", "tool", "duration_ms", "success"))))
res.append(ok("audit attributes member B", any(x["user"].startswith("b") and "Member" not in x["user"] and x["tool"] for x in au)))
print("servers:", [(s["name"], s["status"]) for s in a.get("/api/servers").json()])
print("RESULT:", f"{sum(res)}/{len(res)} passed")
