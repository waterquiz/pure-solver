from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.schemas.user import UserResponse, UserCreate, UserUpdate
from backend.app.auth.dependencies import get_current_admin
from backend.app.auth.security import hash_password

router = APIRouter(prefix="/users", tags=["User Management"])


@router.get("", response_model=List[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    return db.query(User).order_by(User.created_at.desc()).all()


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    existing = db.query(User).filter(
        (User.email == payload.email.lower().strip()) |
        (User.username == payload.username.strip())
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="User with this email or username already exists.")

    new_user = User(
        email=payload.email.lower().strip(),
        username=payload.username.strip(),
        hashed_password=hash_password(payload.password),
        is_active=payload.is_active,
        is_admin=payload.is_admin
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")

    if payload.email is not None:
        target.email = payload.email.lower().strip()
    if payload.username is not None:
        target.username = payload.username.strip()
    if payload.password is not None and payload.password.strip():
        target.hashed_password = hash_password(payload.password)
    if payload.is_active is not None:
        target.is_active = payload.is_active
    if payload.is_admin is not None:
        target.is_admin = payload.is_admin

    db.commit()
    db.refresh(target)
    return target


@router.delete("/{user_id}")
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own admin account.")

    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")

    db.delete(target)
    db.commit()
    return {"success": True, "message": "User deleted successfully."}
