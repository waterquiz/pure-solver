from pydantic import BaseModel, EmailStr
from typing import Optional


class LoginRequest(BaseModel):
    username_or_email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    username: str
    is_admin: bool


class TokenData(BaseModel):
    user_id: Optional[str] = None
    username: Optional[str] = None
    is_admin: bool = False
