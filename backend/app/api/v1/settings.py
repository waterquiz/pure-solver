from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.models.setting import SystemSetting
from backend.app.auth.dependencies import get_current_user

router = APIRouter(prefix="/settings", tags=["Settings"])

AVAILABLE_MODELS = [
    {
        "id": "gemini-2.5-flash",
        "name": "Gemini 2.5 Flash (Balanced Version)",
        "badge": "Recommended (Balanced Speed & Accuracy)",
        "cost_tier": "standard",
        "description": "Optimal balance of lightning speed and vision precision for 9-grid CAPTCHAs"
    },
    {
        "id": "claude-3-5-sonnet",
        "name": "Claude 3.5 Sonnet",
        "badge": "Top Precision",
        "cost_tier": "premium",
        "description": "Highest reasoning & detail recognition"
    },
    {
        "id": "gpt-4o",
        "name": "GPT-4o",
        "badge": "OpenAI Flagship",
        "cost_tier": "premium",
        "description": "Advanced OpenAI multimodal vision model"
    },
    {
        "id": "gpt-4o-mini",
        "name": "GPT-4o Mini",
        "badge": "Fast & Smart",
        "cost_tier": "low",
        "description": "Low latency OpenAI multimodal model"
    },
    {
        "id": "gemini-1.5-flash",
        "name": "Gemini 1.5 Flash",
        "badge": "Fast",
        "cost_tier": "standard",
        "description": "High performance multimodal model"
    },
    {
        "id": "gemini-2.5-flash-lite",
        "name": "Gemini 2.5 Flash Lite",
        "badge": "Fastest",
        "cost_tier": "lowest",
        "description": "Lowest cost & fastest token throughput"
    }
]


class UpdateModelRequest(BaseModel):
    model: str = Field(..., description="Target AI model identifier")


class ModelSettingsResponse(BaseModel):
    active_model: str
    active_model_name: str
    active_badge: str
    available_models: List[Dict[str, Any]]


@router.get("/ai-model", response_model=ModelSettingsResponse)
def get_ai_model_setting(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    setting = db.query(SystemSetting).filter(SystemSetting.key == "ai_model").first()
    active_id = setting.value if setting and setting.value else "gemini-2.5-flash"

    model_info = next((m for m in AVAILABLE_MODELS if m["id"] == active_id), AVAILABLE_MODELS[0])

    return ModelSettingsResponse(
        active_model=model_info["id"],
        active_model_name=model_info["name"],
        active_badge=model_info["badge"],
        available_models=AVAILABLE_MODELS
    )


@router.post("/ai-model", response_model=ModelSettingsResponse)
def update_ai_model_setting(
    payload: UpdateModelRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    valid_ids = [m["id"] for m in AVAILABLE_MODELS]
    if payload.model not in valid_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid model. Must be one of: {', '.join(valid_ids)}"
        )

    setting = db.query(SystemSetting).filter(SystemSetting.key == "ai_model").first()
    if not setting:
        setting = SystemSetting(key="ai_model", value=payload.model)
        db.add(setting)
    else:
        setting.value = payload.model

    db.commit()
    db.refresh(setting)

    model_info = next((m for m in AVAILABLE_MODELS if m["id"] == setting.value), AVAILABLE_MODELS[0])

    return ModelSettingsResponse(
        active_model=model_info["id"],
        active_model_name=model_info["name"],
        active_badge=model_info["badge"],
        available_models=AVAILABLE_MODELS
    )
