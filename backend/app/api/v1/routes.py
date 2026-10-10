from fastapi import APIRouter
from backend.app.api.v1.auth import router as auth_router
from backend.app.api.v1.api_keys import router as api_keys_router
from backend.app.api.v1.images import router as images_router
from backend.app.api.v1.users import router as users_router
from backend.app.api.v1.stats import router as stats_router
from backend.app.api.v1.settings import router as settings_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(auth_router)
api_v1_router.include_router(api_keys_router)
api_v1_router.include_router(images_router)
api_v1_router.include_router(users_router)
api_v1_router.include_router(stats_router)
api_v1_router.include_router(settings_router)

