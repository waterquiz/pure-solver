import io
import uuid
import os
from typing import Tuple, Optional
from PIL import Image as PILImage
from backend.app.config import settings
from backend.app.storage.factory import get_storage


class ImageValidationError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def detect_mime_from_bytes(data: bytes) -> Optional[str]:
    """Detects MIME type from magic byte signatures."""
    if len(data) < 12:
        return None
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return "image/gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"BM"):
        return "image/bmp"
    if data.startswith(b"II*\x00") or data.startswith(b"MM\x00*"):
        return "image/tiff"
    return None


def get_extension_for_mime(mime: str) -> str:
    mapping = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "image/bmp": ".bmp",
        "image/tiff": ".tiff",
    }
    return mapping.get(mime, ".bin")


def validate_and_process_image(
    file_bytes: bytes,
    original_filename: str,
    declared_content_type: Optional[str] = None
) -> Tuple[str, str, int, int, int]:
    """
    Validates image file size, magic bytes signature, and integrity via Pillow.
    Returns: (storage_key, mime_type, file_size, width, height)
    """
    file_size = len(file_bytes)

    # 1. Size check
    if file_size > settings.max_image_size_bytes:
        raise ImageValidationError(
            code="FILE_TOO_LARGE",
            message=f"Maximum image size is {settings.MAX_IMAGE_SIZE_MB} MB.",
            status_code=413
        )
    if file_size == 0:
        raise ImageValidationError(
            code="INVALID_IMAGE",
            message="Uploaded file is empty.",
            status_code=400
        )

    # 2. Magic signature check
    detected_mime = detect_mime_from_bytes(file_bytes)
    if not detected_mime or detected_mime not in settings.ALLOWED_IMAGE_TYPES:
        raise ImageValidationError(
            code="INVALID_IMAGE",
            message="Uploaded file is not a valid image or unsupported image format.",
            status_code=400
        )

    # 3. Pillow integrity & dimension verification
    try:
        with PILImage.open(io.BytesIO(file_bytes)) as img:
            img.verify()
        # Re-open to read dimensions since verify() closes image
        with PILImage.open(io.BytesIO(file_bytes)) as img:
            width, height = img.size
    except Exception as e:
        raise ImageValidationError(
            code="INVALID_IMAGE",
            message=f"Corrupt or unreadable image file: {str(e)}",
            status_code=400
        )

    # 4. Generate secure unique storage key
    ext = get_extension_for_mime(detected_mime)
    unique_id = uuid.uuid4().hex
    storage_key = f"{unique_id[:8]}-{unique_id[8:12]}-{unique_id[12:16]}-{unique_id[16:20]}{ext}"

    # 5. Save to storage provider
    storage = get_storage()
    storage.save_file(file_bytes, storage_key, detected_mime)

    return storage_key, detected_mime, file_size, width, height
