import os
from typing import Optional
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from backend.app.config import settings
from backend.app.storage.base import BaseStorage


class S3Storage(BaseStorage):
    def __init__(self):
        self.bucket = settings.STORAGE_BUCKET
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.STORAGE_ENDPOINT,
            aws_access_key_id=settings.STORAGE_ACCESS_KEY,
            aws_secret_access_key=settings.STORAGE_SECRET_KEY,
            region_name=settings.STORAGE_REGION,
            config=Config(signature_version="s3v4")
        )

    def save_file(self, file_bytes: bytes, storage_key: str, content_type: str) -> str:
        safe_key = os.path.basename(storage_key)
        self.client.put_object(
            Bucket=self.bucket,
            Key=safe_key,
            Body=file_bytes,
            ContentType=content_type
        )
        return safe_key

    def get_file_bytes(self, storage_key: str) -> Optional[bytes]:
        safe_key = os.path.basename(storage_key)
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=safe_key)
            return response["Body"].read()
        except ClientError:
            return None

    def delete_file(self, storage_key: str) -> bool:
        safe_key = os.path.basename(storage_key)
        try:
            self.client.delete_object(Bucket=self.bucket, Key=safe_key)
            return True
        except ClientError:
            return False

    def get_file_url(self, storage_key: str, base_url: str) -> str:
        safe_key = os.path.basename(storage_key)
        # If public CDN or custom domain prefix is specified
        if settings.STORAGE_PUBLIC_URL_PREFIX:
            prefix = settings.STORAGE_PUBLIC_URL_PREFIX.rstrip("/")
            return f"{prefix}/{safe_key}"
        # If storage endpoint is public
        if settings.STORAGE_ENDPOINT and "amazonaws.com" not in settings.STORAGE_ENDPOINT:
            endpoint = settings.STORAGE_ENDPOINT.rstrip("/")
            return f"{endpoint}/{self.bucket}/{safe_key}"
        
        # Fallback to backend media streaming proxy URL or S3 presigned URL
        try:
            presigned = self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": safe_key},
                ExpiresIn=3600 * 24  # 24 hours
            )
            return presigned
        except Exception:
            clean_base = base_url.rstrip("/")
            return f"{clean_base}/media/{safe_key}"

    def check_health(self) -> bool:
        try:
            self.client.head_bucket(Bucket=self.bucket)
            return True
        except Exception:
            return False
