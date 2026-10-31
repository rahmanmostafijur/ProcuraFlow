from functools import lru_cache

from app.core.config import get_settings
from app.storage.base import StorageBackend, StoredObjectNotFoundError, new_storage_key
from app.storage.local import LocalStorage
from app.storage.s3 import S3Storage


@lru_cache
def get_storage() -> StorageBackend:
    settings = get_settings()
    if settings.storage_backend == "s3":
        # Settings validation already guarantees these are present when the backend is s3.
        return S3Storage(
            endpoint_url=settings.s3_endpoint_url or "",
            bucket=settings.s3_bucket or "",
            region=settings.s3_region or "",
            access_key_id=settings.s3_access_key_id or "",
            secret_access_key=settings.s3_secret_access_key or "",
        )
    return LocalStorage(settings.storage_local_path)


__all__ = ["StorageBackend", "StoredObjectNotFoundError", "get_storage", "new_storage_key"]
