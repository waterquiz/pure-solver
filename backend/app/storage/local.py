import os
from typing import Optional
from backend.app.config import settings
from backend.app.storage.base import BaseStorage


class LocalStorage(BaseStorage):
    def __init__(self, upload_dir: Optional[str] = None):
        self.upload_dir = os.path.abspath(upload_dir or settings.STORAGE_LOCAL_DIR)
        os.makedirs(self.upload_dir, exist_ok=True)

    def _resolve_path(self, storage_key: str) -> str:
        safe_name = os.path.basename(storage_key)
        full_path = os.path.abspath(os.path.join(self.upload_dir, safe_name))
        if not full_path.startswith(self.upload_dir):
            raise ValueError("Path traversal attempt detected")
        return full_path

    def save_file(self, file_bytes: bytes, storage_key: str, content_type: str) -> str:
        dest_path = self._resolve_path(storage_key)
        with open(dest_path, "wb") as f:
            f.write(file_bytes)
        return storage_key

    def get_file_bytes(self, storage_key: str) -> Optional[bytes]:
        dest_path = self._resolve_path(storage_key)
        if not os.path.exists(dest_path):
            return None
        with open(dest_path, "rb") as f:
            return f.read()

    def delete_file(self, storage_key: str) -> bool:
        try:
            dest_path = self._resolve_path(storage_key)
            if os.path.exists(dest_path):
                os.remove(dest_path)
                return True
            return False
        except Exception:
            return False

    def get_file_url(self, storage_key: str, base_url: str) -> str:
        safe_name = os.path.basename(storage_key)
        clean_base = base_url.rstrip("/")
        return f"{clean_base}/media/{safe_name}"

    def check_health(self) -> bool:
        try:
            return os.path.exists(self.upload_dir) and os.access(self.upload_dir, os.W_OK)
        except Exception:
            return False
