from abc import ABC, abstractmethod
from typing import Optional


class BaseStorage(ABC):
    @abstractmethod
    def save_file(self, file_bytes: bytes, storage_key: str, content_type: str) -> str:
        """Saves file bytes and returns storage key / identifier."""
        pass

    @abstractmethod
    def get_file_bytes(self, storage_key: str) -> Optional[bytes]:
        """Retrieves raw file bytes."""
        pass

    @abstractmethod
    def delete_file(self, storage_key: str) -> bool:
        """Deletes file from storage."""
        pass

    @abstractmethod
    def get_file_url(self, storage_key: str, base_url: str) -> str:
        """Generates publicly accessible URL or media proxy URL."""
        pass

    @abstractmethod
    def check_health(self) -> bool:
        """Validates storage system readiness."""
        pass
