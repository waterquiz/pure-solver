from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    scopes: Optional[str] = "images:upload,images:read"


class ApiKeyStatusUpdate(BaseModel):
    is_active: bool


class ApiKeyResponse(BaseModel):
    id: str
    name: str
    masked_key: str
    scopes: str
    is_active: bool
    usage_count: int
    last_used_at: Optional[datetime] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ApiKeyCreatedResponse(ApiKeyResponse):
    raw_key: str  # Only returned upon immediate creation!
