import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import bcrypt
import jwt
from backend.app.config import settings


def hash_password(password: str) -> str:
    """Hashes a plaintext password using bcrypt with salt."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against a stored bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Creates a signed JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decodes and validates a JWT access token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload
    except (jwt.PyJWTError, Exception):
        return None


def generate_api_key() -> str:
    """
    Generates a secure, cryptographically random API key with PS_ prefix.
    Example: PS_900a2dbb943ac30d39ba1993ca3614379a04bb
    Length: 43 characters (3 prefix chars 'PS_' + 40 hex chars).
    """
    random_hex = secrets.token_hex(20)
    return f"PS_{random_hex}"


def hash_api_key(api_key: str) -> str:
    """Computes a SHA-256 hash of the API key for secure indexed storage."""
    return hashlib.sha256(api_key.strip().encode("utf-8")).hexdigest()


def mask_api_key(api_key: str) -> str:
    """
    Produces a safe, masked representation of the API key.
    Example: PS_************04bb
    """
    clean_key = api_key.strip()
    if clean_key.startswith("PS_"):
        suffix = clean_key[-4:]
        return f"PS_************{suffix}"
    if clean_key.startswith("sk_live_"):
        suffix = clean_key[-4:]
        return f"sk_live_************{suffix}"
    if len(clean_key) <= 8:
        return "********"
    return f"{clean_key[:3]}************{clean_key[-4:]}"
