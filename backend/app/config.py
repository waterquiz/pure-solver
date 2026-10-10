import os
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    APP_NAME: str = "Remote Image Display API"
    APP_ENV: str = "production"
    SECRET_KEY: str = "super-secret-key-please-override-in-production-random-64-bytes"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Server & Public Domain
    SERVER_HOST: str = "0.0.0.0"
    PORT: int = 8000
    PUBLIC_BASE_URL: str = "http://localhost:8000"

    # Database
    DATABASE_URL: str = Field(default="sqlite:///./data.db")

    # Image Upload Limits & Validation
    MAX_IMAGE_SIZE_MB: int = 10
    MAX_ACTIVE_ON_SCREEN: int = 12
    ALLOWED_IMAGE_TYPES: List[str] = [
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
        "image/bmp",
        "image/tiff",
    ]

    # Rate Limiting
    RATE_LIMIT: int = 100
    RATE_LIMIT_WINDOW: int = 60  # seconds

    # CORS
    CORS_ORIGINS: str = "*"

    # Puter AI Gateway Configuration
    PUTER_AUTH_TOKEN: Optional[str] = None
    DEFAULT_AI_MODEL: str = "gemini-2.5-flash"


    # Storage Provider: "local" or "s3"
    STORAGE_PROVIDER: str = "local"
    STORAGE_LOCAL_DIR: str = "./uploads"

    # S3 Object Storage Configuration
    STORAGE_BUCKET: Optional[str] = None
    STORAGE_ENDPOINT: Optional[str] = None
    STORAGE_ACCESS_KEY: Optional[str] = None
    STORAGE_SECRET_KEY: Optional[str] = None
    STORAGE_REGION: str = "us-east-1"
    STORAGE_PUBLIC_URL_PREFIX: Optional[str] = None

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: Optional[str]) -> str:
        if not v or v.strip() == "":
            return "sqlite:///./data.db"
        # Railway / Heroku postgres url compatibility
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql://", 1)
        return v

    @property
    def cors_origins_list(self) -> List[str]:
        if not self.CORS_ORIGINS or self.CORS_ORIGINS == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def max_image_size_bytes(self) -> int:
        return self.MAX_IMAGE_SIZE_MB * 1024 * 1024


settings = Settings()
