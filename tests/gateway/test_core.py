import os, sys
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../services/gateway"))
from app.auth.api_keys import generate_key, hash_key, encrypt, decrypt
from app.routing.collisions import namespace, split
from app.routing.router import validate_url


def test_key_hash_roundtrip():
    raw, h, pre = generate_key()
    assert raw.startswith("urumi_live_") and h == hash_key(raw) and raw not in h


def test_encrypt():
    assert decrypt(encrypt("secret")) == "secret" and "secret" not in encrypt("secret")


def test_namespacing():
    assert namespace("weather", "get_weather") == "weather__get_weather"
    assert split("woocommerce__list_products") == ("woocommerce", "list_products")


def test_ssrf():
    import pytest
    for url in (
        "http://169.254.169.254/latest",
        "http://metadata.google.internal/computeMetadata/v1",
        "http://user:password@woo-mcp:8000/mcp",
        "file:///etc/passwd",
    ):
        with pytest.raises(ValueError):
            validate_url(url)
    # In-cluster service names and loopback are allowed for local development.
    validate_url("http://woo-mcp:8000/mcp")
    validate_url("http://localhost:8000/mcp")
    validate_url("http://127.0.0.1:8000/mcp")


def test_production_config_fails_closed(monkeypatch):
    from app import config
    monkeypatch.setattr(config, "APP_ENV", "production")
    monkeypatch.setattr(config, "SECRET_KEY", "dev-secret-change-me")
    monkeypatch.setattr(config, "DATABASE_URL", "sqlite:///./urumi.db")
    monkeypatch.setattr(config, "BOOTSTRAP_ADMIN_KEY", "")
    import pytest
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        config.validate_runtime_config()


def test_root_cause_unwraps_nested_exception_groups():
    from app.mcp.client import _root_cause
    inner = ConnectionError("refused")
    assert _root_cause(BaseExceptionGroup("a", [ExceptionGroup("b", [inner])])) is inner
