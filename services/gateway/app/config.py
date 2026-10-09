import os, json

APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./urumi.db")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")  # development fallback only
BOOTSTRAP_ADMIN_EMAIL = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "admin@urumi.local")
BOOTSTRAP_ADMIN_KEY = os.getenv("BOOTSTRAP_ADMIN_KEY", "")
SEED_SERVERS = json.loads(os.getenv("SEED_SERVERS", "[]"))
CONNECT_TIMEOUT = float(os.getenv("UPSTREAM_TIMEOUT", "5"))
CALL_TIMEOUT = float(os.getenv("UPSTREAM_CALL_TIMEOUT", "30"))
HEALTH_INTERVAL = float(os.getenv("HEALTH_INTERVAL", "15"))
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CHAT_MODEL = os.getenv("CHAT_MODEL", "claude-sonnet-5-5")


def validate_runtime_config():
    """Fail closed for production rather than silently using development defaults."""
    if APP_ENV not in {"development", "test", "production"}:
        raise RuntimeError("APP_ENV must be development, test, or production")
    if APP_ENV != "production":
        return
    if SECRET_KEY == "dev-secret-change-me" or len(SECRET_KEY) < 32:
        raise RuntimeError("production requires a random SECRET_KEY of at least 32 characters")
    if not DATABASE_URL.startswith(("postgresql://", "postgresql+")):
        raise RuntimeError("production requires PostgreSQL; SQLite is development/test only")
    if len(BOOTSTRAP_ADMIN_KEY) < 32 or "change-me" in BOOTSTRAP_ADMIN_KEY.lower():
        raise RuntimeError("production requires a unique BOOTSTRAP_ADMIN_KEY of at least 32 characters")
