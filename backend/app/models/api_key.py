import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from backend.app.database import Base


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    key_hash = Column(String(64), unique=True, index=True, nullable=False)
    masked_key = Column(String(64), nullable=False)
    scopes = Column(String(255), default="images:upload,images:read", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    usage_count = Column(Integer, default=0, nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    user = relationship("User", back_populates="api_keys")
    images = relationship("Image", back_populates="api_key")
    api_requests = relationship("ApiRequest", back_populates="api_key")

    def has_scope(self, scope: str) -> bool:
        allowed = [s.strip() for s in (self.scopes or "").split(",") if s.strip()]
        return scope in allowed or "*" in allowed
