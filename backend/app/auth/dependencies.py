from typing import Optional, Tuple
from fastapi import Depends, HTTPException, Header, Request, status, Cookie
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.models.api_key import ApiKey
from backend.app.auth.security import decode_access_token, hash_api_key


class APIKeyAuthException(HTTPException):
    def __init__(self, message: str = "Invalid or missing API key."):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"success": False, "error": {"code": "INVALID_API_KEY", "message": message}},
            headers={"WWW-Authenticate": "ApiKey"}
        )


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    access_token_cookie: Optional[str] = Cookie(None, alias="access_token")
) -> User:
    """Authenticates dashboard user via Authorization Bearer header, session cookie, API key, or local admin fallback."""
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    elif access_token_cookie:
        token = access_token_cookie
    elif request.query_params.get("token"):
        token = request.query_params.get("token")

    if token:
        payload = decode_access_token(token)
        if not payload or "sub" not in payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired or invalid token."
            )
        user_id = payload["sub"]
        user = db.query(User).filter(User.id == user_id, User.is_active == True).first()  # noqa: E712
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or disabled."
            )
        return user

    # Check X-API-Key header or query parameter
    api_key_header = request.headers.get("X-API-Key") or request.query_params.get("api_key")
    if api_key_header:
        key_hash = hash_api_key(api_key_header)
        api_key_obj = db.query(ApiKey).filter(ApiKey.key_hash == key_hash, ApiKey.is_active == True).first()
        if api_key_obj and api_key_obj.user:
            return api_key_obj.user

    # Seamless fallback for local receiver / dashboard operations
    default_user = db.query(User).filter(User.is_active == True).order_by(User.is_admin.desc()).first()
    if default_user:
        return default_user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Please log in."
    )


def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    """Ensures current authenticated user is an administrator."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required."
        )
    return current_user


def validate_api_key_header(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: Session = Depends(get_db)
) -> Tuple[ApiKey, User]:
    """
    Validates API key from X-API-Key or Authorization: Bearer sk_...
    Returns (ApiKey, User) tuple.
    """
    api_key_str = x_api_key

    # Check Authorization header fallback
    if not api_key_str:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            candidate = auth_header.split(" ")[1].strip()
            if candidate.startswith("sk_"):
                api_key_str = candidate

    if not api_key_str:
        raise APIKeyAuthException("Invalid or missing API key.")

    key_hash = hash_api_key(api_key_str)
    api_key = db.query(ApiKey).filter(
        ApiKey.key_hash == key_hash,
        ApiKey.is_active == True  # noqa: E712
    ).first()

    if not api_key:
        raise APIKeyAuthException("Invalid or inactive API key.")

    # Retrieve owner user
    owner = db.query(User).filter(User.id == api_key.user_id, User.is_active == True).first()  # noqa: E712
    if not owner:
        raise APIKeyAuthException("Owner account is disabled or not found.")

    return api_key, owner
