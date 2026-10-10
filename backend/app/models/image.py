import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.app.database import Base


class Image(Base):
    __tablename__ = "images"

    id = Column(String(36), primary_key=True, default=lambda: f"img_{uuid.uuid4().hex[:12]}")
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    api_key_id = Column(String(36), ForeignKey("api_keys.id", ondelete="SET NULL"), nullable=True, index=True)
    original_filename = Column(String(255), nullable=False)
    storage_key = Column(String(255), unique=True, nullable=False, index=True)
    mime_type = Column(String(50), nullable=False)
    file_size = Column(Integer, nullable=False)  # In bytes
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    client_id = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)
    status = Column(String(20), default="active", nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    # Relationships
    user = relationship("User", back_populates="images")
    api_key = relationship("ApiKey", back_populates="images")
