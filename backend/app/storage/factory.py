from backend.app.config import settings
from backend.app.storage.base import BaseStorage
from backend.app.storage.local import LocalStorage
from backend.app.storage.s3 import S3Storage

_storage_instance: BaseStorage = None


def get_storage() -> BaseStorage:
    """Returns singleton instance of the configured storage provider."""
    global _storage_instance
    if _storage_instance is None:
        if settings.STORAGE_PROVIDER.lower() == "s3":
            _storage_instance = S3Storage()
        else:
            _storage_instance = LocalStorage()
    return _storage_instance


def reset_storage_instance():
    """Allows testing or reconfiguring storage dynamically."""
    global _storage_instance
    _storage_instance = None
