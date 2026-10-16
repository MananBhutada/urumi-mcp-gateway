"""Small async WooCommerce REST client. Credentials stay inside this service."""
import base64
import hashlib
import hmac
import os
import secrets
import time
from urllib.parse import quote, urlsplit, urlunsplit

import httpx

BASE = os.getenv("WOO_BASE_URL", "http://wordpress").rstrip("/")
CK = os.getenv("WOO_CONSUMER_KEY", "")
CS = os.getenv("WOO_CONSUMER_SECRET", "")
HOST = os.getenv("WOO_HOST_HEADER", "")
TIMEOUT = float(os.getenv("WOO_TIMEOUT_SECONDS", "15"))


class WooError(Exception):
    """Safe, user-facing WooCommerce integration error."""


def _rfc3986(value: object) -> str:
    return quote(str(value), safe="-._~")


def _oauth_base_url(path: str) -> str:
    parsed = urlsplit(BASE)
    host = HOST or parsed.netloc
    return urlunsplit((parsed.scheme, host, f"/wp-json/wc/v3{path}", "", ""))


def _oauth_params(method: str, path: str, params: dict) -> dict:
    oauth = {
        "oauth_consumer_key": CK,
        "oauth_nonce": secrets.token_hex(16),
        "oauth_signature_method": "HMAC-SHA256",
        "oauth_timestamp": str(int(time.time())),
    }
    signing_params = {**params, **oauth}
    normalized_pairs = sorted(
        (_rfc3986(key), _rfc3986(value))
        for key, value in signing_params.items()
    )
    normalized_query = "&".join(
        f"{key}={value}" for key, value in normalized_pairs
    )
    string_to_sign = "&".join(
        [
            method.upper(),
            _rfc3986(_oauth_base_url(path)),
            _rfc3986(normalized_query),
        ]
    )
    digest = hmac.new(f"{CS}&".encode(), string_to_sign.encode(), hashlib.sha256).digest()
    oauth["oauth_signature"] = base64.b64encode(digest).decode()
    return oauth


def _validate_configuration() -> None:
    parsed = urlsplit(BASE)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise WooError("WOO_BASE_URL must be an absolute http(s) URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise WooError("WOO_BASE_URL must not contain credentials, query, or fragment")
    if not CK or not CS:
        raise WooError("WooCommerce REST credentials are not configured")
    if TIMEOUT <= 0 or TIMEOUT > 60:
        raise WooError("WOO_TIMEOUT_SECONDS must be between 0 and 60")


def _validate_path(path: str) -> str:
    if not isinstance(path, str) or not path.startswith("/") or path.startswith("//"):
        raise WooError("WooCommerce API path must be an absolute API path")
    if "://" in path or "\\" in path or any(part == ".." for part in path.split("/")):
        raise WooError("Invalid WooCommerce API path")
    return path


async def request(method: str, path: str, params=None, json=None):
    _validate_configuration()
    path = _validate_path(path)
    method = method.upper()
    query = dict(params or {})
    query.update(_oauth_params(method, path, query))
    headers = {"Host": HOST} if HOST else {}
    url = f"{BASE}/wp-json/wc/v3{path}"
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=False) as client:
            response = await client.request(method, url, params=query, json=json, headers=headers)
    except httpx.TimeoutException as exc:
        raise WooError("WooCommerce request timed out") from exc
    except httpx.HTTPError as exc:
        raise WooError(f"WooCommerce connection failed ({type(exc).__name__})") from exc

    if response.status_code >= 400:
        # Never echo response bodies: plugins/proxies can include sensitive request details.
        if response.status_code in {401, 403}:
            raise WooError(f"WooCommerce rejected the REST credentials or permissions (HTTP {response.status_code})")
        if response.status_code == 404:
            raise WooError("WooCommerce resource was not found (HTTP 404)")
        raise WooError(f"WooCommerce API returned HTTP {response.status_code}")
    try:
        return response.json()
    except ValueError as exc:
        raise WooError("WooCommerce returned an invalid JSON response") from exc
