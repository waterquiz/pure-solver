from pydantic import BaseModel


class DashboardStats(BaseModel):
    total_images: int
    uploads_today: int
    uploads_this_month: int
    total_api_requests: int
    failed_requests: int
    active_api_keys: int
    active_ai_model: str = "gemini-2.5-flash"
    active_screen_images: int = 0
    queued_images: int = 0
    max_screen_limit: int = 12

