"""MinIO object storage adapter."""

from io import BytesIO

from minio import Minio
from minio.error import S3Error

from wrc_pipeline.config import AppConfig


class MinioStorage:
    """Expose simple bucket, upload, download, and existence operations."""

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.from_env()
        self.client = Minio(
            self.config.minio_endpoint,
            access_key=self.config.minio_access_key,
            secret_key=self.config.minio_secret_key,
            secure=self.config.minio_secure,
        )

    def ensure_buckets(self) -> None:
        """Ensure both landing and processed buckets exist."""
        for bucket in (
            self.config.minio_landing_bucket,
            self.config.minio_processed_bucket,
        ):
            if not self.client.bucket_exists(bucket):
                self.client.make_bucket(bucket)

    def object_exists(self, bucket: str, object_name: str) -> bool:
        """Return whether an object exists without downloading it."""
        try:
            self.client.stat_object(bucket, object_name)
        except S3Error as exc:
            if exc.code in {"NoSuchKey", "NoSuchObject", "NotFound"}:
                return False
            raise
        return True

    def upload_bytes(
        self,
        bucket: str,
        object_name: str,
        content: bytes,
        content_type: str,
    ) -> None:
        """Upload exact bytes to an object path."""
        self.client.put_object(
            bucket,
            object_name,
            BytesIO(content),
            length=len(content),
            content_type=content_type,
        )

    def download_bytes(self, bucket: str, object_name: str) -> bytes:
        """Download an object and close its response safely."""
        response = self.client.get_object(bucket, object_name)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()
