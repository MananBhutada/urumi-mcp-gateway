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
    with pytest.raises(ValueError): validate_url("http://169.254.169.254/latest")
    with pytest.raises(ValueError): validate_url("file:///etc/passwd")
    validate_url("http://woo-mcp:8000/mcp")


def test_root_cause_unwraps_nested_exception_groups():
    from app.mcp.client import _root_cause
    inner = ConnectionError("refused")
    assert _root_cause(BaseExceptionGroup("a", [ExceptionGroup("b", [inner])])) is inner
