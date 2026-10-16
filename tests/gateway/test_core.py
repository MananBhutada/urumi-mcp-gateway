import os, sys
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../services/gateway"))
from app.auth.api_keys import generate_key, hash_key, encrypt, decrypt
from app.routing.collisions import namespace, split
from app.routing.router import validate_url


def test_key_hash_roundtrip():
    raw, h, pre = generate_key()
    assert raw.startswith("urumi_live_") and h == hash_key(raw) and raw not in h


def test_user_from_token_rejects_unknown_and_revoked_keys():
    import pytest
    from fastapi import HTTPException
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from sqlalchemy.pool import StaticPool
    from app.db.session import Base
    from app.models.tables import ApiKey, User
    from app.auth.rbac import user_from_token

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(email="admin@example.com", role="ADMIN")
        db.add(user)
        db.flush()
        active_key = "urumi_live_active_key_for_test"
        revoked_key = "urumi_live_revoked_key_for_test"
        db.add(ApiKey(user_id=user.id, key_hash=hash_key(active_key), key_prefix=active_key[:14]))
        db.add(ApiKey(user_id=user.id, key_hash=hash_key(revoked_key), key_prefix=revoked_key[:14], revoked=True))
        db.commit()

        assert user_from_token(db, active_key).email == "admin@example.com"
        with pytest.raises(HTTPException) as unknown:
            user_from_token(db, "urumi_live_unknown_key_for_test")
        assert unknown.value.status_code == 401
        with pytest.raises(HTTPException) as revoked:
            user_from_token(db, revoked_key)
        assert revoked.value.status_code == 401


def test_bootstrap_does_not_replace_existing_admin_key(monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app import main
    from app.db.session import Base
    from app.models.tables import ApiKey, User

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    old_key = "urumi_live_existing_admin_key_for_test"
    replacement_key = "urumi_live_replacement_admin_key_for_test"
    with factory() as db:
        admin = User(email="admin@example.com", name="Admin", role="ADMIN")
        db.add(admin)
        db.flush()
        db.add(ApiKey(user_id=admin.id, key_hash=hash_key(old_key), key_prefix=old_key[:14]))
        db.commit()

    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setattr(main, "SessionLocal", factory)
    monkeypatch.setattr(main, "BOOTSTRAP_ADMIN_KEY", replacement_key)
    monkeypatch.setattr(main, "BOOTSTRAP_ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setattr(main, "SEED_SERVERS", [])
    monkeypatch.setattr(main, "validate_runtime_config", lambda: None)

    main.bootstrap()

    with factory() as db:
        assert db.query(User).filter_by(email="admin@example.com").count() == 1
        keys = db.query(ApiKey).filter_by(user_id=db.query(User).filter_by(email="admin@example.com").one().id).all()
        assert len(keys) == 1
        assert keys[0].key_hash == hash_key(old_key)
        assert keys[0].key_hash != hash_key(replacement_key)


def test_encrypt():
    assert decrypt(encrypt("secret")) == "secret" and "secret" not in encrypt("secret")


def test_namespacing():
    assert namespace("weather", "get_weather") == "weather__get_weather"
    assert split("woocommerce__list_products") == ("woocommerce", "list_products")


def test_tool_permissions_default_deny_members_and_preserve_admin_access(monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from sqlalchemy.pool import StaticPool
    from app.db.session import Base
    from app.models.tables import ToolPermission, User
    from app.auth.rbac import tool_allowed

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        assert tool_allowed(db, "MEMBER", "weather__get_weather") is False
        assert tool_allowed(db, "ADMIN", "weather__get_weather") is True

        db.add(ToolPermission(role="MEMBER", tool="weather__get_weather", allowed=True))
        db.add(ToolPermission(role="MEMBER", tool="currency__list_rates", allowed=False))
        db.commit()
        assert tool_allowed(db, "MEMBER", "weather__get_weather") is True
        assert tool_allowed(db, "MEMBER", "currency__list_rates") is False


def test_tool_catalog_uses_request_database_session_and_shared_registry(monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from sqlalchemy.pool import StaticPool
    from app.db.session import Base
    from app.models.tables import McpServer, McpToolCache, ToolPermission, User
    from app.routing import router

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        member = User(email="member@example.com", role="MEMBER")
        db.add(member)
        db.add(McpServer(name="weather", url="http://weather-mcp:8000/mcp", enabled=True))
        db.add(ToolPermission(role="MEMBER", tool="weather__get_weather", allowed=True))
        db.add(McpToolCache(server_name="weather", tools_json=[{
            "name": "get_weather", "description": "Current weather", "inputSchema": {"type": "object"}
        }]))
        db.commit()

        monkeypatch.setattr(router, "SessionLocal", lambda: (_ for _ in ()).throw(AssertionError("opened another DB session")))
        assert [tool["name"] for tool in router.tools_for(member, db)] == ["weather__get_weather"]
        server = db.query(McpServer).filter_by(name="weather").one()
        server.enabled = False
        db.commit()
        assert router.tools_for(member, db) == []


def test_ungranted_member_tool_call_is_denied_before_upstream(monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session, sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.db.session import Base
    from app.models.tables import McpServer, User
    from app.routing import router

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with Session(engine) as db:
        member = User(email="member@example.com", role="MEMBER")
        db.add(member)
        db.add(McpServer(name="weather", url="http://weather-mcp:8000/mcp", enabled=True))
        db.commit()
        db.refresh(member)

    audited = []
    monkeypatch.setattr(router, "SessionLocal", factory)
    monkeypatch.setattr(router.audit, "record", lambda *args, **kwargs: audited.append((args, kwargs)))
    async def unexpected_call(*args, **kwargs):
        raise AssertionError("upstream must not be called for a denied tool")
    monkeypatch.setattr(router.client, "call_tool", unexpected_call)

    import asyncio
    result = asyncio.run(router.execute(member, "weather__get_weather", {"city": "Pune"}))
    assert result["isError"] is True
    assert "may not call" in result["content"][0]["text"]
    assert len(audited) == 1
    assert audited[0][0][5] is False


def test_upstream_refresh_persists_and_clears_shared_tool_catalog(monkeypatch):
    import asyncio
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session, sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.db.session import Base
    from app.models.tables import McpServer, McpToolCache
    from app.routing import router

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with Session(engine) as db:
        server = McpServer(name="weather", url="http://weather-mcp:8000/mcp", enabled=True)
        db.add(server)
        db.commit()
        server_id = server.id

    monkeypatch.setattr(router, "SessionLocal", factory)
    async def list_tools(*args):
        return [{"name": "get_weather", "description": "Current weather", "inputSchema": {"type": "object"}}]
    monkeypatch.setattr(router.client, "list_tools", list_tools)
    asyncio.run(router.refresh_server(server_id))
    with Session(engine) as db:
        cache = db.get(McpToolCache, "weather")
        assert cache.tools_json[0]["name"] == "get_weather"
        assert db.get(McpServer, server_id).status == "connected"

    async def failed_list(*args):
        raise TimeoutError("upstream unavailable")
    monkeypatch.setattr(router.client, "list_tools", failed_list)
    asyncio.run(router.refresh_server(server_id))
    with Session(engine) as db:
        assert db.get(McpToolCache, "weather") is None
        assert db.get(McpServer, server_id).status == "unreachable"


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


def test_mcp_jsonrpc_request_validation():
    from app.mcp.server import _is_valid_request
    assert _is_valid_request({"jsonrpc": "2.0", "id": 1, "method": "ping"})
    assert _is_valid_request({"jsonrpc": "2.0", "method": "notifications/initialized"})
    assert not _is_valid_request({"jsonrpc": "1.0", "id": 1, "method": "ping"})
    assert not _is_valid_request({"jsonrpc": "2.0", "method": "", "id": 1})
    assert not _is_valid_request({"jsonrpc": "2.0", "method": "ping", "id": True})
    assert not _is_valid_request({"jsonrpc": "2.0", "method": "tools/call", "params": []})


def test_mcp_endpoint_handles_parse_errors_and_auth(monkeypatch):
    import asyncio
    import json
    from app.mcp import server

    class FakeRequest:
        def __init__(self, body, authorization="Bearer test"):
            self.body = body
            self.headers = {"authorization": authorization}
        async def json(self):
            if isinstance(self.body, Exception):
                raise self.body
            return self.body

    class FakeUser:
        id = 1
        role = "MEMBER"

    monkeypatch.setattr(server, "user_from_token", lambda db, token: FakeUser())
    parse = asyncio.run(server.mcp_endpoint(FakeRequest(ValueError("bad json")), None))
    assert parse.status_code == 200
    assert json.loads(parse.body)["error"]["code"] == -32700

    invalid = asyncio.run(server.mcp_endpoint(FakeRequest({"jsonrpc": "1.0", "id": 1, "method": "ping"}), None))
    assert json.loads(invalid.body)["error"]["code"] == -32600

    unsupported = asyncio.run(server.mcp_endpoint(FakeRequest({"jsonrpc": "2.0", "id": 2, "method": "does/not/exist"}), None))
    assert json.loads(unsupported.body)["error"]["code"] == -32601

    bad_call = asyncio.run(server.mcp_endpoint(FakeRequest({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": [], "arguments": {}}}), None))
    assert json.loads(bad_call.body)["error"]["code"] == -32602
