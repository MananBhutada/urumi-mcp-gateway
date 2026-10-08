import hmac, hashlib, secrets, base64
from cryptography.fernet import Fernet
from ..config import SECRET_KEY

PREFIX = "urumi_live_"

def hash_key(raw: str) -> str:
    return hmac.new(SECRET_KEY.encode(), raw.encode(), hashlib.sha256).hexdigest()

def generate_key() -> tuple[str, str, str]:
    """returns (raw, hash, prefix). Raw is shown once and never stored."""
    raw = PREFIX + secrets.token_urlsafe(32)
    return raw, hash_key(raw), raw[:14]

_fernet = Fernet(base64.urlsafe_b64encode(hashlib.sha256(("enc:" + SECRET_KEY).encode()).digest()))
def encrypt(s: str) -> str: return _fernet.encrypt(s.encode()).decode() if s else ""
def decrypt(s: str) -> str: return _fernet.decrypt(s.encode()).decode() if s else ""
