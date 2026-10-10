from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.models.image import Image
from backend.app.models.api_request import ApiRequest
from backend.app.models.api_key import ApiKey
from backend.app.models.user import User
from backend.app.models.setting import SystemSetting
from backend.app.schemas.stats import DashboardStats



def get_dashboard_stats(db: Session, current_user: User) -> DashboardStats:
    now = datetime.now(timezone.utc)
    today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)

    # Base query for images
    img_q = db.query(Image)
    if not current_user.is_admin:
        img_q = img_q.filter(Image.user_id == current_user.id)

    total_images = img_q.count()
    uploads_today = img_q.filter(Image.created_at >= today_start).count()
    uploads_this_month = img_q.filter(Image.created_at >= month_start).count()
    active_screen_images = img_q.filter(Image.status == "active").count()
    queued_images = img_q.filter(Image.status == "queued").count()

    # Active API keys
    key_q = db.query(ApiKey).filter(ApiKey.is_active == True)  # noqa: E712
    if not current_user.is_admin:
        key_q = key_q.filter(ApiKey.user_id == current_user.id)
    active_api_keys = key_q.count()

    # API requests
    req_q = db.query(ApiRequest)
    if not current_user.is_admin:
        # User's API keys
        user_key_ids = [k.id for k in db.query(ApiKey.id).filter(ApiKey.user_id == current_user.id).all()]
        req_q = req_q.filter(ApiRequest.api_key_id.in_(user_key_ids))

    total_api_requests = req_q.count()
    failed_requests = req_q.filter(ApiRequest.status_code >= 400).count()

    # Active AI Model
    model_setting = db.query(SystemSetting).filter(SystemSetting.key == "ai_model").first()
    active_ai_model = model_setting.value if model_setting and model_setting.value else "gemini-2.5-flash"

    from backend.app.config import settings

    return DashboardStats(
        total_images=total_images,
        uploads_today=uploads_today,
        uploads_this_month=uploads_this_month,
        total_api_requests=total_api_requests,
        failed_requests=failed_requests,
        active_api_keys=active_api_keys,
        active_ai_model=active_ai_model,
        active_screen_images=active_screen_images,
        queued_images=queued_images,
        max_screen_limit=settings.MAX_ACTIVE_ON_SCREEN,
    )
