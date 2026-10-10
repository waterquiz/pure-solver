import os
import io
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import (
    FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException,
    Query, Request, Response, status
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.app.config import settings
from backend.app.database import engine, init_db, get_db
from backend.app.api.v1.routes import api_v1_router
from backend.app.auth.security import decode_access_token
from backend.app.models.user import User
from backend.app.storage.factory import get_storage
from backend.app.websocket.connection_manager import manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure database tables are created
    init_db()
    # Ensure local upload directory exists if using local storage
    if settings.STORAGE_PROVIDER.lower() == "local":
        os.makedirs(os.path.abspath(settings.STORAGE_LOCAL_DIR), exist_ok=True)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Production-ready Secure Image Upload API with Real-time Web Dashboard",
    lifespan=lifespan,
    docs_url="/api/swagger",  # Put OpenAPI Swagger at /api/swagger so /docs is our full custom interactive documentation!
    redoc_url=None
)

from backend.app.auth.dependencies import APIKeyAuthException

@app.exception_handler(APIKeyAuthException)
async def api_key_auth_exception_handler(request: Request, exc: APIKeyAuthException):
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.detail,
        headers=exc.headers
    )

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Static Files & Templates
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATIC_DIR = os.path.join(BASE_DIR, "frontend", "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "frontend", "templates")

os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Mount API v1
app.include_router(api_v1_router)


# -----------------------------------------------------------------------------
# Health Check Endpoint
# -----------------------------------------------------------------------------
@app.get("/health", tags=["System"])
def health_check(db: Session = Depends(get_db)):
    # 1. Check Database connection
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    # 2. Check Storage provider health
    storage = get_storage()
    storage_ok = storage.check_health()

    status_str = "ok" if (db_ok and storage_ok) else "degraded"
    return {
        "status": status_str,
        "database": "connected" if db_ok else "unreachable",
        "storage": "available" if storage_ok else "unavailable",
        "storage_provider": settings.STORAGE_PROVIDER,
        "environment": settings.APP_ENV
    }


# -----------------------------------------------------------------------------
# Media Serving Endpoint
# -----------------------------------------------------------------------------
@app.get("/media/{storage_key}", tags=["Media"])
def serve_media(storage_key: str):
    """Securely streams image bytes from configured storage provider."""
    storage = get_storage()
    data = storage.get_file_bytes(storage_key)
    if not data:
        raise HTTPException(status_code=404, detail="Image file not found.")

    # Determine content type based on extension
    ext = os.path.splitext(storage_key)[1].lower()
    content_type_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
        ".tiff": "image/tiff",
    }
    content_type = content_type_map.get(ext, "application/octet-stream")

    return Response(
        content=data,
        media_type=content_type,
        headers={
            "Cache-Control": "public, max-age=86400",
            "X-Content-Type-Options": "nosniff"
        }
    )


# -----------------------------------------------------------------------------
# Real-time WebSocket Endpoint
# -----------------------------------------------------------------------------
@app.websocket("/ws/dashboard")
async def websocket_dashboard_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    # Extract token from query param or cookie
    auth_token = token or websocket.cookies.get("access_token")
    if not auth_token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    payload = decode_access_token(auth_token)
    if not payload or "sub" not in payload:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user_id = payload["sub"]
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()  # noqa: E712
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(websocket, user_id=user.id, is_admin=user.is_admin)

    try:
        # Await incoming heartbeat messages (pings)
        while True:
            data = await websocket.receive_text()
            if data == "ping" or '"ping"' in data:
                await websocket.send_text('{"type": "pong"}')
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id=user.id)
    except Exception:
        manager.disconnect(websocket, user_id=user.id)


# -----------------------------------------------------------------------------
# Frontend Page Routes (Protected & Public)
# -----------------------------------------------------------------------------
@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(content=b"", media_type="image/x-icon")


@app.get("/", response_class=RedirectResponse)
def index():
    return RedirectResponse(url="/dashboard", status_code=302)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html", context={"app_name": settings.APP_NAME})


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request):
    return templates.TemplateResponse(request=request, name="dashboard.html", context={"app_name": settings.APP_NAME})


@app.get("/dashboard/api-keys", response_class=HTMLResponse)
def api_keys_page(request: Request):
    return templates.TemplateResponse(request=request, name="api_keys.html", context={"app_name": settings.APP_NAME})


@app.get("/dashboard/api-test", response_class=HTMLResponse)
def api_test_page(request: Request):
    return templates.TemplateResponse(request=request, name="api_test.html", context={"app_name": settings.APP_NAME})


@app.get("/dashboard/users", response_class=HTMLResponse)
def users_page(request: Request):
    return templates.TemplateResponse(request=request, name="users.html", context={"app_name": settings.APP_NAME})


@app.get("/dashboard/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    return templates.TemplateResponse(request=request, name="settings.html", context={"app_name": settings.APP_NAME})



@app.get("/docs", response_class=HTMLResponse)
def documentation_page(request: Request):
    return templates.TemplateResponse(request=request, name="docs.html", context={"app_name": settings.APP_NAME})
