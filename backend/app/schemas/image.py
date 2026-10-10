from datetime import datetime
from typing import Optional, Any, Dict, List
from pydantic import BaseModel


class ImageDetail(BaseModel):
    id: str
    filename: str
    mime_type: str
    size: int
    url: str
    width: Optional[int] = None
    height: Optional[int] = None
    client_id: Optional[str] = None
    description: Optional[str] = None
    text: Optional[str] = None
    created_at: datetime
    api_key_masked: Optional[str] = None
    api_key_name: Optional[str] = None
    matched_cells: Optional[List[int]] = None
    output: Optional[str] = None
    ai_result: Optional[Dict[str, Any]] = None
    status: Optional[str] = "active"


class ImageUploadResponse(BaseModel):
    success: bool = True
    message: str = "Image uploaded successfully."
    image: ImageDetail
    image_id: Optional[str] = None
    client_id: Optional[str] = None
    status: Optional[str] = "active"
    matched_cells: Optional[List[int]] = None
    output: Optional[str] = None


class ImageResultResponse(BaseModel):
    image_id: str
    client_id: Optional[str] = None
    status: str
    text: Optional[str] = None
    matched_cells: Optional[List[int]] = None
    output: Optional[str] = None
    model: Optional[str] = None



class ImageListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    images: List[ImageDetail]


class ImageErrorDetail(BaseModel):
    code: str
    message: str


class ImageErrorResponse(BaseModel):
    success: bool = False
    error: ImageErrorDetail
