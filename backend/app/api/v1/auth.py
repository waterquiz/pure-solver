from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.schemas.auth import LoginRequest, TokenResponse
from backend.app.schemas.user import UserResponse
from backend.app.auth.security import verify_password, create_access_token
from backend.app.auth.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    # Support login with either email or username
    user = db.query(User).filter(
        (User.email == payload.username_or_email.lower().strip()) |
        (User.username == payload.username_or_email.strip())
    ).first()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email or password."
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled. Please contact administrator."
        )

    access_token = create_access_token(
        data={"sub": user.id, "username": user.username, "is_admin": user.is_admin}
    )

    # Set secure HTTP-only cookie for browser dashboard convenience
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=60 * 60 * 24 * 7,
        samesite="lax",
        secure=False  # Set to True in HTTPS production if required
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        username=user.username,
        is_admin=user.is_admin
    )


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(key="access_token")
    return {"success": True, "message": "Successfully logged out."}


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    return current_user
