from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.schemas.stats import DashboardStats
from backend.app.services.stats_service import get_dashboard_stats
from backend.app.auth.dependencies import get_current_user

router = APIRouter(prefix="/stats", tags=["Statistics"])


@router.get("", response_model=DashboardStats)
def fetch_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return get_dashboard_stats(db, current_user)
