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


def _bootstrap_test_environment(monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app import main
    from app.db.session import Base

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setattr(main, "SessionLocal", factory)
    monkeypatch.setattr(main, "BOOTSTRAP_ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setattr(main, "BOOTSTRAP_ADMIN_KEY", "urumi_live_configured_admin_key_for_test")
    monkeypatch.setattr(main, "BOOTSTRAP_ADMIN_KEY_RECOVERY", False)
    monkeypatch.setattr(main, "SEED_SERVERS", [])
    monkeypatch.setattr(main, "validate_runtime_config", lambda: None)
    return main, factory


def test_bootstrap_uses_transaction_scoped_postgres_advisory_lock():
    from types import SimpleNamespace
    from app import main

    class FakeSession:
        def __init__(self):
            self.statements = []

        def get_bind(self):
            return SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

        def execute(self, statement, parameters):
            self.statements.append((str(statement), parameters))

    db = FakeSession()
    main._lock_bootstrap(db)

    assert db.statements == [(
        "SELECT pg_advisory_xact_lock(:lock_id)",
        {"lock_id": main.BOOTSTRAP_LOCK_ID},
    )]


def test_bootstrap_creates_admin_and_key_on_first_start(monkeypatch):
    from app.models.tables import ApiKey, User
    from app.auth.rbac import user_from_token

    main, factory = _bootstrap_test_environment(monkeypatch)
    configured_key = main.BOOTSTRAP_ADMIN_KEY
    main.bootstrap()

    with factory() as db:
        admin = db.query(User).filter_by(email="admin@example.com").one()
        assert admin.role == "ADMIN"
        assert db.query(ApiKey).filter_by(user_id=admin.id).count() == 1
        assert user_from_token(db, configured_key).id == admin.id


def test_bootstrap_repeated_startup_is_idempotent(monkeypatch):
    from app.models.tables import ApiKey, User

    main, factory = _bootstrap_test_environment(monkeypatch)
    main.bootstrap()
    main.bootstrap()

    with factory() as db:
        admin = db.query(User).filter_by(email="admin@example.com").one()
        assert db.query(ApiKey).filter_by(user_id=admin.id).count() == 1


def test_bootstrap_does_not_reconcile_mismatched_key_without_explicit_recovery(monkeypatch):
    from app.models.tables import ApiKey, User

    main, factory = _bootstrap_test_environment(monkeypatch)
    old_key = "urumi_live_existing_admin_key_for_test"
    with factory() as db:
        admin = User(email="admin@example.com", name="Admin", role="ADMIN")
        db.add(admin)
        db.flush()
        db.add(ApiKey(user_id=admin.id, key_hash=hash_key(old_key), key_prefix=old_key[:14]))
        db.commit()

    main.bootstrap()

    with factory() as db:
        admin = db.query(User).filter_by(email="admin@example.com").one()
        keys = db.query(ApiKey).filter_by(user_id=admin.id).all()
        assert len(keys) == 1
        assert keys[0].key_hash == hash_key(old_key)
        assert keys[0].key_hash != hash_key(main.BOOTSTRAP_ADMIN_KEY)


def test_explicit_bootstrap_recovery_adds_configured_key_and_preserves_other_data(monkeypatch):
    from app.models.tables import ApiKey, AuditLog, McpServer, User
    from app.auth.rbac import user_from_token

    main, factory = _bootstrap_test_environment(monkeypatch)
    main.BOOTSTRAP_ADMIN_KEY_RECOVERY = True
    old_admin_key = "urumi_live_existing_admin_key_for_test"
    unrelated_admin_key = "urumi_live_other_admin_key_for_test"
    member_key = "urumi_live_member_key_for_test"
    with factory() as db:
        admin = User(email="admin@example.com", name="Existing Admin", role="ADMIN")
        member = User(email="member@example.com", name="Member", role="MEMBER")
        db.add_all([admin, member])
        db.flush()
        db.add_all([
            ApiKey(user_id=admin.id, key_hash=hash_key(old_admin_key), key_prefix=old_admin_key[:14]),
            ApiKey(user_id=admin.id, key_hash=hash_key(unrelated_admin_key), key_prefix=unrelated_admin_key[:14]),
            ApiKey(user_id=member.id, key_hash=hash_key(member_key), key_prefix=member_key[:14]),
            McpServer(name="preserved-server", url="http://example.invalid/mcp"),
            AuditLog(user_id=admin.id, user_email=admin.email, tool_name="preserved-tool"),
        ])
        db.commit()

    main.bootstrap()
    main.bootstrap()

    with factory() as db:
        admin = db.query(User).filter_by(email="admin@example.com").one()
        member = db.query(User).filter_by(email="member@example.com").one()
        admin_keys = db.query(ApiKey).filter_by(user_id=admin.id).all()
        assert {key.key_hash for key in admin_keys} == {
            hash_key(old_admin_key),
            hash_key(unrelated_admin_key),
            hash_key(main.BOOTSTRAP_ADMIN_KEY),
        }
        assert all(not key.revoked for key in admin_keys)
        assert user_from_token(db, main.BOOTSTRAP_ADMIN_KEY).id == admin.id
        assert user_from_token(db, old_admin_key).id == admin.id
        assert user_from_token(db, unrelated_admin_key).id == admin.id
        assert user_from_token(db, member_key).id == member.id
        assert db.query(McpServer).filter_by(name="preserved-server").count() == 1
        assert db.query(AuditLog).filter_by(tool_name="preserved-tool").count() == 1


def test_explicit_recovery_refuses_to_reactivate_a_revoked_bootstrap_key(monkeypatch):
    import pytest
    from app.models.tables import ApiKey, User

    main, factory = _bootstrap_test_environment(monkeypatch)
    main.BOOTSTRAP_ADMIN_KEY_RECOVERY = True
    with factory() as db:
        admin = User(email="admin@example.com", role="ADMIN")
        db.add(admin)
        db.flush()
        db.add(ApiKey(
            user_id=admin.id,
            key_hash=hash_key(main.BOOTSTRAP_ADMIN_KEY),
            key_prefix=main.BOOTSTRAP_ADMIN_KEY[:14],
            revoked=True,
        ))
        db.commit()

    with pytest.raises(RuntimeError, match="configured bootstrap key is revoked"):
        main.bootstrap()

    with factory() as db:
        admin = db.query(User).filter_by(email="admin@example.com").one()
        key = db.query(ApiKey).filter_by(user_id=admin.id).one()
        assert key.revoked is True


def test_explicit_recovery_refuses_non_admin_bootstrap_email(monkeypatch):
    import pytest
    from app.models.tables import ApiKey, User

    main, factory = _bootstrap_test_environment(monkeypatch)
    monkeypatch.setattr(main, "BOOTSTRAP_ADMIN_KEY_RECOVERY", True)
    with factory() as db:
        member = User(email="admin@example.com", role="MEMBER")
        db.add(member)
        db.commit()

    with pytest.raises(RuntimeError, match="existing account to have the ADMIN role"):
        main.bootstrap()

    with factory() as db:
        assert db.query(User).filter_by(email="admin@example.com").one().role == "MEMBER"
        assert db.query(ApiKey).count() == 0


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
    from app.models.tables import McpServer, McpToolCache, User
    from app.routing import router

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with Session(engine) as db:
        member = User(email="member@example.com", role="MEMBER")
        db.add(member)
        db.add(McpServer(name="weather", url="http://weather-mcp:8000/mcp", enabled=True))
        db.add(McpToolCache(server_name="weather", tools_json=[{
            "name": "get_weather", "description": "Current weather",
            "inputSchema": {"type": "object"},
        }]))
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
    assert result["content"][0]["text"] == "tool is not permitted for this user"
    assert len(audited) == 1
    assert audited[0][0][5] is False


def test_gateway_refuses_undiscovered_tool_without_echoing_or_auditing_input(monkeypatch):
    import asyncio
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session, sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.db.session import Base
    from app.models.tables import McpServer, McpToolCache, User
    from app.routing import router

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with Session(engine) as db:
        admin = User(email="admin@example.com", role="ADMIN")
        db.add(admin)
        db.add(McpServer(name="weather", url="http://weather-mcp:8000/mcp", enabled=True))
        db.add(McpToolCache(server_name="weather", tools_json=[{
            "name": "get_weather", "description": "Current weather",
            "inputSchema": {"type": "object"},
        }]))
        db.commit()
        db.refresh(admin)

    audited = []
    monkeypatch.setattr(router, "SessionLocal", factory)
    monkeypatch.setattr(router.audit, "record", lambda *args, **kwargs: audited.append(args))

    async def unexpected_call(*args, **kwargs):
        raise AssertionError("undiscovered tool must not reach upstream")

    monkeypatch.setattr(router.client, "call_tool", unexpected_call)
    supplied_name = "weather__private-token-value"
    result = asyncio.run(router.execute(admin, supplied_name, {}))

    assert result["isError"] is True
    assert "private-token-value" not in result["content"][0]["text"]
    assert audited[0][1:3] == ("", "<unknown>")
    assert "private-token-value" not in str(audited[0])
    malformed = asyncio.run(router.execute(admin, "private-token-value", {}))
    assert malformed["isError"] is True
    assert "private-token-value" not in malformed["content"][0]["text"]
    assert "private-token-value" not in str(audited[1])


def test_gateway_executes_discovered_tool_for_granted_member(monkeypatch):
    import asyncio
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session, sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.db.session import Base
    from app.models.tables import McpServer, McpToolCache, ToolPermission, User
    from app.routing import router

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with Session(engine) as db:
        member = User(email="member@example.com", role="MEMBER")
        db.add(member)
        db.add(McpServer(name="weather", url="http://weather-mcp:8000/mcp", enabled=True))
        db.add(McpToolCache(server_name="weather", tools_json=[{
            "name": "get_weather", "description": "Current weather",
            "inputSchema": {"type": "object"},
        }]))
        db.add(ToolPermission(role="MEMBER", tool="weather__get_weather", allowed=True))
        db.commit()
        db.refresh(member)

    calls, audited = [], []
    monkeypatch.setattr(router, "SessionLocal", factory)
    monkeypatch.setattr(router, "decrypt", lambda _: "")
    monkeypatch.setattr(router.audit, "record", lambda *args, **kwargs: audited.append(args))

    async def fake_call(url, credential, tool, arguments, timeout):
        calls.append((url, tool, arguments))
        return {"content": [{"type": "text", "text": "18 C"}], "isError": False}

    monkeypatch.setattr(router.client, "call_tool", fake_call)
    result = asyncio.run(router.execute(member, "weather__get_weather", {"city": "Pune"}))

    assert result["content"][0]["text"] == "18 C"
    assert calls == [("http://weather-mcp:8000/mcp", "get_weather", {"city": "Pune"})]
    assert audited[0][5] is True


def test_mcp_endpoint_dispatches_authenticated_tool_call(monkeypatch):
    import asyncio
    import json
    from app.mcp import server

    class FakeRequest:
        headers = {"authorization": "Bearer test-key"}

        async def json(self):
            return {
                "jsonrpc": "2.0", "id": 7, "method": "tools/call",
                "params": {"name": "woocommerce__get_products", "arguments": {"per_page": 5}},
            }

    class FakeUser:
        role = "ADMIN"

    called = []
    monkeypatch.setattr(server, "user_from_token", lambda db, token: FakeUser())

    async def fake_execute(user, name, arguments, source):
        called.append((user.role, name, arguments, source))
        return {"content": [{"type": "text", "text": "products"}], "isError": False}

    monkeypatch.setattr(server.R, "execute", fake_execute)
    response = asyncio.run(server.mcp_endpoint(FakeRequest(), None))

    assert called == [("ADMIN", "woocommerce__get_products", {"per_page": 5}, "mcp")]
    assert json.loads(response.body)["result"]["isError"] is False


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
    from app.api.admin import _safe_url
    for url in (
        "http://169.254.169.254/latest",
        "http://metadata.google.internal/computeMetadata/v1",
        "http://user:password@woo-mcp:8000/mcp",
        "file:///etc/passwd",
        "http://woo-mcp:8000/mcp?token=secret",
        "http://woo-mcp:8000/mcp#secret",
    ):
        with pytest.raises(ValueError):
            validate_url(url)
    # In-cluster service names and loopback are allowed for local development.
    validate_url("http://woo-mcp:8000/mcp")
    validate_url("http://localhost:8000/mcp")
    validate_url("http://127.0.0.1:8000/mcp")
    with pytest.raises(ValueError):
        validate_url("http://woo-mcp:invalid/mcp")
    safe_url = _safe_url("https://user:secret@example.invalid/mcp?token=secret#fragment")
    assert safe_url == "https://example.invalid/mcp"
    assert "secret" not in safe_url


def test_upstream_errors_are_sanitized_in_tool_response_and_audit(monkeypatch):
    import asyncio
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session, sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.db.session import Base
    from app.models.tables import McpServer, McpToolCache, User
    from app.mcp.client import UpstreamError
    from app.routing import router

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with Session(engine) as db:
        admin = User(email="admin@example.com", role="ADMIN")
        db.add(admin)
        db.add(McpServer(name="weather", url="http://weather-mcp:8000/mcp", enabled=True))
        db.add(McpToolCache(server_name="weather", tools_json=[{
            "name": "get_weather", "description": "Current weather",
            "inputSchema": {"type": "object"},
        }]))
        db.commit()

    audited = []
    monkeypatch.setattr(router, "SessionLocal", factory)
    monkeypatch.setattr(router, "decrypt", lambda _: "")
    monkeypatch.setattr(router.audit, "record", lambda *args, **kwargs: audited.append((args, kwargs)))

    async def failed_call(*args, **kwargs):
        raise UpstreamError("connection_error", "https://internal/?token=never-return-this")

    monkeypatch.setattr(router.client, "call_tool", failed_call)
    with factory() as db:
        admin = db.query(User).filter_by(email="admin@example.com").one()
        result = asyncio.run(router.execute(admin, "weather__get_weather", {}, "mcp"))

    message = result["content"][0]["text"]
    assert message == "Could not connect to upstream MCP server"
    assert "never-return-this" not in message
    assert audited[0][0][6] == message
    assert "never-return-this" not in audited[0][0][6]
    assert router.safe_stored_error("connection_error: https://internal/?token=never-return-this") == message


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
