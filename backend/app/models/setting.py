from sqlalchemy import Column, String
from backend.app.database import Base


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key = Column(String(50), primary_key=True, index=True)
    value = Column(String(255), nullable=False)
