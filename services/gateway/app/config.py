import os, json

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./urumi.db")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")           # HMAC for API keys + Fernet derivation
BOOTSTRAP_ADMIN_EMAIL = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "admin@urumi.local")
BOOTSTRAP_ADMIN_KEY = os.getenv("BOOTSTRAP_ADMIN_KEY", "")            # raw admin key, hashed on startup
SEED_SERVERS = json.loads(os.getenv("SEED_SERVERS", "[]"))            # [{"name","url","credential"}]
CONNECT_TIMEOUT = float(os.getenv("UPSTREAM_TIMEOUT", "5"))
CALL_TIMEOUT = float(os.getenv("UPSTREAM_CALL_TIMEOUT", "30"))
HEALTH_INTERVAL = float(os.getenv("HEALTH_INTERVAL", "15"))
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CHAT_MODEL = os.getenv("CHAT_MODEL", "claude-sonnet-5-5")
