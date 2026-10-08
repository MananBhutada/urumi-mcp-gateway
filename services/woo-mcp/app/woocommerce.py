"""Thin async WooCommerce REST client. Credentials never leave this service."""
import os, httpx

BASE = os.getenv("WOO_BASE_URL", "http://wordpress").rstrip("/")
CK = os.getenv("WOO_CONSUMER_KEY", "")
CS = os.getenv("WOO_CONSUMER_SECRET", "")
HOST = os.getenv("WOO_HOST_HEADER", "")  # WP canonical host, e.g. store.urumi.local

class WooError(Exception):
    pass

async def request(method: str, path: str, params=None, json=None):
    params = dict(params or {})
    params.update({"consumer_key": CK, "consumer_secret": CS})  # query auth works over plain HTTP in-cluster
    headers = {"Host": HOST} if HOST else {}
    async with httpx.AsyncClient(timeout=15, follow_redirects=False) as c:
        r = await c.request(method, f"{BASE}/wp-json/wc/v3{path}", params=params, json=json, headers=headers)
    if r.status_code >= 400:
        raise WooError(f"WooCommerce {r.status_code}: {r.text[:300]}")
    return r.json()
