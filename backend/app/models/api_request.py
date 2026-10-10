import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from backend.app.database import Base


class ApiRequest(Base):
    __tablename__ = "api_requests"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    api_key_id = Column(String(36), ForeignKey("api_keys.id", ondelete="SET NULL"), nullable=True, index=True)
    endpoint = Column(String(255), nullable=False)
    http_method = Column(String(10), nullable=False)
    status_code = Column(Integer, nullable=False, index=True)
    request_duration_ms = Column(Float, nullable=False)
    file_size = Column(Integer, nullable=True)
    ip_address = Column(String(45), nullable=True)
    error_code = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    # Relationships
    api_key = relationship("ApiKey", back_populates="api_requests")
