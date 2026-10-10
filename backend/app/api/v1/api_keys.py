from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.models.api_key import ApiKey
from backend.app.schemas.api_key import ApiKeyCreate, ApiKeyResponse, ApiKeyCreatedResponse, ApiKeyStatusUpdate
from backend.app.auth.dependencies import get_current_user
from backend.app.auth.security import generate_api_key, hash_api_key, mask_api_key

router = APIRouter(prefix="/api-keys", tags=["API Keys"])


@router.get("", response_model=List[ApiKeyResponse])
def list_api_keys(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(ApiKey)
    if not current_user.is_admin:
        query = query.filter(ApiKey.user_id == current_user.id)
    return query.order_by(ApiKey.created_at.desc()).all()


@router.post("", response_model=ApiKeyCreatedResponse, status_code=status.HTTP_201_CREATED)
def create_api_key(
    payload: ApiKeyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Generate cryptographic live API key
    raw_key = generate_api_key()
    key_hash = hash_api_key(raw_key)
    masked = mask_api_key(raw_key)

    new_key = ApiKey(
        user_id=current_user.id,
        name=payload.name.strip(),
        key_hash=key_hash,
        masked_key=masked,
        scopes=payload.scopes or "images:upload,images:read",
        is_active=True,
        usage_count=0
    )
    db.add(new_key)
    db.commit()
    db.refresh(new_key)

    # Return raw_key once only
    return ApiKeyCreatedResponse(
        id=new_key.id,
        name=new_key.name,
        masked_key=new_key.masked_key,
        scopes=new_key.scopes,
        is_active=new_key.is_active,
        usage_count=new_key.usage_count,
        last_used_at=new_key.last_used_at,
        created_at=new_key.created_at,
        raw_key=raw_key
    )


@router.patch("/{key_id}/status", response_model=ApiKeyResponse)
def update_api_key_status(
    key_id: str,
    payload: ApiKeyStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(ApiKey).filter(ApiKey.id == key_id)
    if not current_user.is_admin:
        query = query.filter(ApiKey.user_id == current_user.id)
    key_obj = query.first()

    if not key_obj:
        raise HTTPException(status_code=404, detail="API key not found.")

    key_obj.is_active = payload.is_active
    db.commit()
    db.refresh(key_obj)
    return key_obj


@router.delete("/{key_id}", status_code=status.HTTP_200_OK)
def revoke_api_key(
    key_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(ApiKey).filter(ApiKey.id == key_id)
    if not current_user.is_admin:
        query = query.filter(ApiKey.user_id == current_user.id)
    key_obj = query.first()

    if not key_obj:
        raise HTTPException(status_code=404, detail="API key not found.")

    db.delete(key_obj)
    db.commit()
    return {"success": True, "message": "API key revoked and deleted successfully."}
