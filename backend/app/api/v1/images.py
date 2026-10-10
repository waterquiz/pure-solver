import time
import os
import json
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from fastapi import (
    APIRouter, Depends, File, Form, UploadFile, Request, HTTPException,
    status, Query, Response
)
from fastapi.responses import JSONResponse, StreamingResponse
import io
from sqlalchemy.orm import Session


from backend.app.config import settings
from backend.app.database import get_db, SessionLocal
from backend.app.models.user import User
from backend.app.models.api_key import ApiKey
from backend.app.models.image import Image
from backend.app.models.api_request import ApiRequest
from backend.app.schemas.image import (
    ImageUploadResponse, ImageListResponse, ImageDetail, ImageErrorResponse, ImageResultResponse
)
from backend.app.auth.dependencies import validate_api_key_header, get_current_user
from backend.app.services.image_service import validate_and_process_image, ImageValidationError
from backend.app.services.rate_limiter import rate_limiter
from backend.app.services.puter_service import (
    register_waiter, resolve_waiter, wait_for_ai_result, call_puter_ai_backend
)
from backend.app.storage.factory import get_storage
from backend.app.websocket.connection_manager import manager


logger = logging.getLogger(__name__)

# Tracks image IDs with an active pending auto-deletion to avoid duplicates
_scheduled_deletions: set = set()


async def promote_next_queued_image_async(owner_id: Optional[str] = None, db: Optional[Session] = None):
    """
    Checks if active images on screen are below MAX_ACTIVE_ON_SCREEN (default 12).
    If so, promotes the oldest queued image to active and broadcasts it to the dashboard.
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    try:
        active_count = db.query(Image).filter(Image.status == "active").count()
        if active_count < settings.MAX_ACTIVE_ON_SCREEN:
            next_img = db.query(Image).filter(Image.status == "queued").order_by(Image.created_at.asc()).first()
            if next_img:
                next_img.status = "active"
                db.commit()
                db.refresh(next_img)

                storage = get_storage()
                base_url = settings.PUBLIC_BASE_URL.rstrip("/")
                image_url = storage.get_file_url(next_img.storage_key, base_url)

                event_payload = {
                    "id": next_img.id,
                    "filename": next_img.original_filename,
                    "url": image_url,
                    "mime_type": next_img.mime_type,
                    "size": next_img.file_size,
                    "width": next_img.width,
                    "height": next_img.height,
                    "client_id": next_img.client_id,
                    "description": next_img.description,
                    "text": next_img.description or next_img.original_filename,
                    "status": "active",
                    "created_at": next_img.created_at.isoformat(),
                    "api_key_masked": next_img.api_key.masked_key if next_img.api_key else None,
                    "api_key_name": next_img.api_key.name if next_img.api_key else None
                }

                target_owner = owner_id or next_img.user_id
                await manager.broadcast_image_event(
                    owner_user_id=target_owner,
                    event_type="image_received",
                    image_data=event_payload
                )

                queued_count = db.query(Image).filter(Image.status == "queued").count()
                await manager.broadcast_image_event(
                    owner_user_id=target_owner,
                    event_type="queue_updated",
                    image_data={"queued_count": queued_count, "active_count": active_count + 1}
                )
                logger.info(f"Promoted queued image {next_img.id} (client: {next_img.client_id}) to active screen slot.")
    except Exception as e:
        logger.error(f"Error promoting queued image: {e}")
    finally:
        if close_db:
            db.close()


async def _delayed_delete_worker(image_id: str, owner_id: str, delay_seconds: float):
    """Wait delay_seconds then delete image from storage and DB, broadcasting event."""
    try:
        await asyncio.sleep(delay_seconds)
        db = SessionLocal()
        try:
            img = db.query(Image).filter(Image.id == image_id).first()
            if img:
                storage = get_storage()
                try:
                    storage.delete_file(img.storage_key)
                except Exception as e:
                    logger.warning(f"Failed to delete storage file {img.storage_key}: {e}")

                db.delete(img)
                db.commit()
                logger.info(f"Auto-deleted image {image_id} from website after {delay_seconds}s delay.")

                # Broadcast deletion to dashboard WebSocket
                await manager.broadcast_image_event(
                    owner_user_id=owner_id,
                    event_type="image_deleted",
                    image_data={"id": image_id}
                )

                # Promote next waiting queued image to screen to take the freed slot!
                await promote_next_queued_image_async(owner_id, db=db)
        except Exception as db_err:
            db.rollback()
            logger.error(f"Error auto-deleting image {image_id}: {db_err}")
        finally:
            db.close()
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Exception in _delayed_delete_worker for {image_id}: {e}")
    finally:
        _scheduled_deletions.discard(image_id)


def schedule_delayed_deletion(image_id: str, owner_id: str, delay_seconds: float = 4.0):
    """Schedule asynchronous auto-deletion of an image after delay_seconds (e.g. 3-5 seconds)."""
    if image_id in _scheduled_deletions:
        return
    _scheduled_deletions.add(image_id)
    try:
        asyncio.create_task(_delayed_delete_worker(image_id, owner_id, delay_seconds))
    except RuntimeError:
        pass


router = APIRouter(prefix="/images", tags=["Images"])


def log_api_request(
    db: Session,
    api_key_id: Optional[str],
    endpoint: str,
    method: str,
    status_code: int,
    duration_ms: float,
    file_size: Optional[int],
    ip: Optional[str],
    error_code: Optional[str] = None
):
    try:
        log_entry = ApiRequest(
            api_key_id=api_key_id,
            endpoint=endpoint,
            http_method=method,
            status_code=status_code,
            request_duration_ms=round(duration_ms, 2),
            file_size=file_size,
            ip_address=ip,
            error_code=error_code
        )
        db.add(log_entry)
        db.commit()
    except Exception:
        db.rollback()


@router.post(
    "",
    response_model=ImageUploadResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ImageErrorResponse},
        401: {"model": ImageErrorResponse},
        413: {"model": ImageErrorResponse},
        429: {"model": ImageErrorResponse},
        500: {"model": ImageErrorResponse},
    }
)
async def upload_image(
    request: Request,
    file: UploadFile = File(...),
    filename: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    text: Optional[str] = Form(None),
    caption: Optional[str] = Form(None),
    title: Optional[str] = Form(None),
    client_id: Optional[str] = Form(None),
    metadata: Optional[str] = Form(None),
    wait_for_ai: bool = Query(True, description="Wait for Puter AI vision analysis to finish"),
    auto_delete_seconds: int = Query(4, ge=0, le=300, description="Auto-delete image from website N seconds after output is sent (default: 4 seconds, 0 to disable)"),
    timeout_seconds: float = Query(30.0, ge=5.0, le=60.0, description="Max seconds to await Puter AI vision analysis (allows 12+ concurrent browsers)"),
    auth_info: tuple = Depends(validate_api_key_header),
    db: Session = Depends(get_db)
):
    start_time = time.time()
    api_key, owner_user = auth_info
    client_ip = request.client.host if request.client else "unknown"

    # 1. Scope verification
    if not api_key.has_scope("images:upload"):
        duration_ms = (time.time() - start_time) * 1000
        log_api_request(db, api_key.id, "/api/v1/images", "POST", 403, duration_ms, 0, client_ip, "FORBIDDEN")
        return JSONResponse(
            status_code=403,
            content={"success": False, "error": {"code": "FORBIDDEN", "message": "API key lacks images:upload permission."}}
        )

    # 2. Rate limiting check
    if not rate_limiter.is_allowed(api_key.id):
        duration_ms = (time.time() - start_time) * 1000
        log_api_request(db, api_key.id, "/api/v1/images", "POST", 429, duration_ms, 0, client_ip, "RATE_LIMITED")
        return JSONResponse(
            status_code=429,
            content={"success": False, "error": {"code": "RATE_LIMITED", "message": "Too many requests. Rate limit exceeded."}}
        )

    # 3. Read uploaded bytes
    try:
        file_bytes = await file.read()
    except Exception:
        duration_ms = (time.time() - start_time) * 1000
        log_api_request(db, api_key.id, "/api/v1/images", "POST", 400, duration_ms, 0, client_ip, "READ_ERROR")
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": {"code": "INVALID_IMAGE", "message": "Unable to read uploaded file."}}
        )

    file_size = len(file_bytes)
    orig_name = filename or file.filename or "image.png"

    # 4. Image validation & storage processing
    try:
        storage_key, mime_type, size, width, height = validate_and_process_image(
            file_bytes=file_bytes,
            original_filename=orig_name,
            declared_content_type=file.content_type
        )
    except ImageValidationError as ive:
        duration_ms = (time.time() - start_time) * 1000
        log_api_request(db, api_key.id, "/api/v1/images", "POST", ive.status_code, duration_ms, file_size, client_ip, ive.code)
        return JSONResponse(
            status_code=ive.status_code,
            content={"success": False, "error": {"code": ive.code, "message": ive.message}}
        )
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        log_api_request(db, api_key.id, "/api/v1/images", "POST", 500, duration_ms, file_size, client_ip, "SERVER_ERROR")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": {"code": "SERVER_ERROR", "message": f"Internal server error: {str(e)}"}}
        )

    # 5. Save database record
    storage = get_storage()
    # Resolve base URL (respecting PUBLIC_BASE_URL or host header)
    base_url = settings.PUBLIC_BASE_URL or str(request.base_url).rstrip("/")
    image_url = storage.get_file_url(storage_key, base_url)

    final_text = (text or caption or title or description or "").strip()

    active_count = db.query(Image).filter(Image.status == "active").count()
    initial_status = "active" if active_count < settings.MAX_ACTIVE_ON_SCREEN else "queued"

    new_image = Image(
        user_id=owner_user.id,
        api_key_id=api_key.id,
        original_filename=orig_name,
        storage_key=storage_key,
        mime_type=mime_type,
        file_size=size,
        width=width,
        height=height,
        client_id=client_id,
        description=final_text or None,
        metadata_json=metadata,
        status=initial_status
    )
    db.add(new_image)

    # Increment usage counter and update last used
    api_key.usage_count += 1
    api_key.last_used_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(new_image)

    duration_ms = (time.time() - start_time) * 1000
    log_api_request(db, api_key.id, "/api/v1/images", "POST", 201, duration_ms, size, client_ip)

    # 6. Broadcast real-time WebSocket event IF slot is active on screen
    if initial_status == "active":
        event_payload = {
            "id": new_image.id,
            "filename": new_image.original_filename,
            "url": image_url,
            "mime_type": new_image.mime_type,
            "size": new_image.file_size,
            "width": new_image.width,
            "height": new_image.height,
            "client_id": new_image.client_id,
            "description": new_image.description,
            "text": new_image.description or new_image.original_filename,
            "status": "active",
            "created_at": new_image.created_at.isoformat(),
            "api_key_masked": api_key.masked_key,
            "api_key_name": api_key.name
        }
        await manager.broadcast_image_event(
            owner_user_id=owner_user.id,
            event_type="image_received",
            image_data=event_payload
        )
    else:
        # Buffer in backend queue
        queued_count = db.query(Image).filter(Image.status == "queued").count()
        await manager.broadcast_image_event(
            owner_user_id=owner_user.id,
            event_type="queue_updated",
            image_data={"queued_count": queued_count, "active_count": active_count}
        )
        logger.info(f"Image {new_image.id} (client: {new_image.client_id}) buffered in backend queue ({queued_count} queued).")

    # 7. Coordinate Puter AI Vision Inference
    ai_data = None
    target_query = final_text or orig_name

    # Try direct backend Puter AI if PUTER_AUTH_TOKEN is configured and active
    if settings.PUTER_AUTH_TOKEN and initial_status == "active":
        ai_data = await call_puter_ai_backend(
            file_bytes, mime_type, target_query, model=settings.DEFAULT_AI_MODEL
        )
        if ai_data:
            meta_dict = {}
            try:
                if new_image.metadata_json:
                    meta_dict = json.loads(new_image.metadata_json)
            except Exception:
                pass
            meta_dict["ai_result"] = ai_data
            new_image.metadata_json = json.dumps(meta_dict)
            db.commit()

    # Otherwise await result from connected browser dashboard Puter worker
    if not ai_data and wait_for_ai and manager.has_active_connections(owner_user.id):
        register_waiter(new_image.id)
        # Wait up to timeout_seconds for Puter browser worker
        # (If queued, when an earlier image finishes & deletes, promote_next_queued_image_async
        # will promote this image to active on screen and dashboard worker solves it!)
        ai_data = await wait_for_ai_result(new_image.id, timeout_seconds=timeout_seconds)
        if ai_data:
            meta_dict = {}
            try:
                if new_image.metadata_json:
                    meta_dict = json.loads(new_image.metadata_json)
            except Exception:
                pass
            meta_dict["ai_result"] = ai_data
            new_image.metadata_json = json.dumps(meta_dict)
            db.commit()

    matched_cells = ai_data.get("matched_cells") if ai_data else None
    output_str = ai_data.get("raw_output") if ai_data else None
    if ai_data:
        msg = "Image uploaded and analyzed successfully by Puter AI."
    elif initial_status == "queued":
        msg = "Image buffered in backend queue (waiting for open screen slot)."
    else:
        msg = "Image uploaded successfully. Puter AI analysis queued."

    # Schedule auto-deletion from website after 3-5 seconds (default 4s) once output is delivered
    if auto_delete_seconds > 0 and ai_data:
        schedule_delayed_deletion(new_image.id, owner_user.id, float(auto_delete_seconds))

    return ImageUploadResponse(
        success=True,
        message=msg,
        image=ImageDetail(
            id=new_image.id,
            filename=new_image.original_filename,
            mime_type=new_image.mime_type,
            size=new_image.file_size,
            url=image_url,
            width=new_image.width,
            height=new_image.height,
            client_id=new_image.client_id,
            description=new_image.description,
            text=new_image.description or new_image.original_filename,
            status=new_image.status,
            created_at=new_image.created_at,
            api_key_masked=api_key.masked_key,
            api_key_name=api_key.name,
            matched_cells=matched_cells,
            output=output_str,
            ai_result=ai_data
        ),
        image_id=new_image.id,
        client_id=new_image.client_id,
        status=new_image.status,
        matched_cells=matched_cells,
        output=output_str
    )


def extract_ai_data(img_obj: Image):
    meta = {}
    try:
        if img_obj.metadata_json:
            meta = json.loads(img_obj.metadata_json)
    except Exception:
        pass
    ai_res = meta.get("ai_result") if isinstance(meta, dict) else None
    matched = ai_res.get("matched_cells") if isinstance(ai_res, dict) else None
    return matched, ai_res


@router.get("", response_model=ImageListResponse)
def list_images(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=100),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query("active", description="Filter by status: 'active', 'queued', or 'all'"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Image)
    if not current_user.is_admin:
        query = query.filter(Image.user_id == current_user.id)

    if status and status != "all":
        query = query.filter(Image.status == status)

    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            (Image.original_filename.ilike(term)) |
            (Image.client_id.ilike(term)) |
            (Image.description.ilike(term))
        )

    total = query.count()
    images_records = query.order_by(Image.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    storage = get_storage()
    base_url = settings.PUBLIC_BASE_URL or str(request.base_url).rstrip("/")

    items = []
    for img in images_records:
        matched, ai_res = extract_ai_data(img)
        items.append(
            ImageDetail(
                id=img.id,
                filename=img.original_filename,
                mime_type=img.mime_type,
                size=img.file_size,
                url=storage.get_file_url(img.storage_key, base_url),
                width=img.width,
                height=img.height,
                client_id=img.client_id,
                description=img.description,
                text=img.description or img.original_filename,
                status=img.status,
                created_at=img.created_at,
                api_key_masked=img.api_key.masked_key if img.api_key else None,
                api_key_name=img.api_key.name if img.api_key else "Direct / Unknown",
                matched_cells=matched,
                ai_result=ai_res
            )
        )

    return ImageListResponse(
        total=total,
        page=page,
        page_size=page_size,
        images=items
    )


@router.get("/{image_id}", response_model=ImageDetail)
def get_image(
    image_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Image).filter(Image.id == image_id)
    if not current_user.is_admin:
        query = query.filter(Image.user_id == current_user.id)
    img = query.first()

    if not img:
        raise HTTPException(status_code=404, detail="Image not found.")

    storage = get_storage()
    base_url = settings.PUBLIC_BASE_URL or str(request.base_url).rstrip("/")
    matched, ai_res = extract_ai_data(img)

    return ImageDetail(
        id=img.id,
        filename=img.original_filename,
        mime_type=img.mime_type,
        size=img.file_size,
        url=storage.get_file_url(img.storage_key, base_url),
        width=img.width,
        height=img.height,
        client_id=img.client_id,
        description=img.description,
        text=img.description or img.original_filename,
        status=img.status,
        created_at=img.created_at,
        api_key_masked=img.api_key.masked_key if img.api_key else None,
        api_key_name=img.api_key.name if img.api_key else None,
        matched_cells=matched,
        ai_result=ai_res
    )


@router.get("/{image_id}/download")
def download_image(
    image_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Image).filter(Image.id == image_id)
    if not current_user.is_admin:
        query = query.filter(Image.user_id == current_user.id)
    img = query.first()

    if not img:
        raise HTTPException(status_code=404, detail="Image not found.")

    storage = get_storage()
    file_bytes = storage.get_file_bytes(img.storage_key)
    if not file_bytes:
        raise HTTPException(status_code=404, detail="Image binary data not found in storage.")

    safe_filename = os.path.basename(img.original_filename).replace('"', '')
    return StreamingResponse(
        io.BytesIO(file_bytes),
        media_type=img.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{safe_filename}"'
        }
    )


@router.delete("/clear/all")
@router.post("/clear/all")
async def clear_all_images(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Image)
    if not current_user.is_admin:
        query = query.filter(Image.user_id == current_user.id)
    imgs = query.all()
    storage = get_storage()
    count = len(imgs)
    for img in imgs:
        try:
            storage.delete_file(img.storage_key)
        except Exception:
            pass
        db.delete(img)
    db.commit()

    await manager.broadcast_image_event(
        owner_user_id=current_user.id,
        event_type="all_images_cleared",
        image_data={"cleared_count": count}
    )

    return {"success": True, "message": f"Successfully cleared {count} images."}


@router.delete("/{image_id}")
async def delete_image(
    image_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Image).filter(Image.id == image_id)
    if not current_user.is_admin:
        query = query.filter(Image.user_id == current_user.id)
    img = query.first()

    if not img:
        raise HTTPException(status_code=404, detail="Image not found.")

    storage = get_storage()
    storage.delete_file(img.storage_key)

    owner_id = img.user_id
    db.delete(img)
    db.commit()

    # Broadcast image deletion event
    await manager.broadcast_image_event(
        owner_user_id=owner_id,
        event_type="image_deleted",
        image_data={"id": image_id}
    )

    # Promote next queued image from backend queue if open slot available
    await promote_next_queued_image_async(owner_id, db=db)

    return {"success": True, "message": "Image deleted successfully."}


class SaveAiResultPayload(BaseModel):
    matched_cells: List[int]
    raw_output: str
    model: Optional[str] = "gemini-2.5-flash"


@router.post("/{image_id}/ai-result")
async def save_image_ai_result(
    image_id: str,
    payload: SaveAiResultPayload,
    auto_delete_seconds: int = Query(4, ge=0, le=300, description="Auto-delete image from website N seconds after output is saved (default: 4s)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Image).filter(Image.id == image_id)
    if not current_user.is_admin:
        query = query.filter(Image.user_id == current_user.id)
    img = query.first()

    if not img:
        raise HTTPException(status_code=404, detail="Image not found.")

    meta = {}
    try:
        if img.metadata_json:
            meta = json.loads(img.metadata_json)
    except Exception:
        pass

    ai_data = {
        "matched_cells": payload.matched_cells,
        "raw_output": payload.raw_output,
        "model": payload.model,
        "analyzed_at": datetime.now(timezone.utc).isoformat()
    }
    meta["ai_result"] = ai_data
    img.metadata_json = json.dumps(meta)
    db.commit()

    # Unblock any waiting upload_image request!
    resolve_waiter(img.id, ai_data)

    # Broadcast real-time WebSocket event so open dashboards update the card live!
    await manager.broadcast_image_event(
        owner_user_id=img.user_id,
        event_type="ai_result_ready",
        image_data={
            "id": img.id,
            "matched_cells": payload.matched_cells,
            "raw_output": payload.raw_output,
            "model": payload.model
        }
    )

    # Schedule auto-deletion from website after 3-5 seconds (default 4s)
    if auto_delete_seconds > 0:
        schedule_delayed_deletion(img.id, img.user_id, float(auto_delete_seconds))

    return {"success": True, "image_id": img.id, "ai_result": ai_data}


@router.get("/latest/result", response_model=ImageResultResponse)
def get_latest_image_result(
    db: Session = Depends(get_db)
):
    img = db.query(Image).order_by(Image.created_at.desc()).first()
    if not img:
        raise HTTPException(status_code=404, detail="No images found.")

    matched, ai_res = extract_ai_data(img)
    status_str = "completed" if matched is not None else "processing"
    raw_output = ai_res.get("raw_output") if ai_res else None
    model_name = ai_res.get("model") if ai_res else None

    return ImageResultResponse(
        image_id=img.id,
        client_id=img.client_id,
        status=status_str,
        text=img.description or img.original_filename,
        matched_cells=matched,
        output=raw_output,
        model=model_name
    )


@router.get("/by-client/{client_id}/latest/result", response_model=ImageResultResponse)
def get_client_latest_image_result(
    client_id: str,
    db: Session = Depends(get_db)
):
    """Retrieve the latest Puter AI result strictly for a specific browser/client."""
    img = db.query(Image).filter(Image.client_id == client_id).order_by(Image.created_at.desc()).first()
    if not img:
        raise HTTPException(status_code=404, detail=f"No images found for browser/client: {client_id}")

    matched, ai_res = extract_ai_data(img)
    status_str = "completed" if matched is not None else "processing"
    raw_output = ai_res.get("raw_output") if ai_res else None
    model_name = ai_res.get("model") if ai_res else None

    return ImageResultResponse(
        image_id=img.id,
        client_id=img.client_id,
        status=status_str,
        text=img.description or img.original_filename,
        matched_cells=matched,
        output=raw_output,
        model=model_name
    )


@router.get("/{image_id}/result", response_model=ImageResultResponse)
def get_image_result(
    image_id: str,
    db: Session = Depends(get_db)
):
    img = db.query(Image).filter(Image.id == image_id).first()
    if not img:
        raise HTTPException(status_code=404, detail="Image not found.")

    matched, ai_res = extract_ai_data(img)
    status_str = "completed" if matched is not None else "processing"
    raw_output = ai_res.get("raw_output") if ai_res else None
    model_name = ai_res.get("model") if ai_res else None

    return ImageResultResponse(
        image_id=img.id,
        client_id=img.client_id,
        status=status_str,
        text=img.description or img.original_filename,
        matched_cells=matched,
        output=raw_output,
        model=model_name
    )


