from functools import lru_cache

from app.core.config import get_settings
from app.storage.base import StorageBackend, StoredObjectNotFoundError, new_storage_key
from app.storage.local import LocalStorage


@lru_cache
def get_storage() -> StorageBackend:
    settings = get_settings()
    return LocalStorage(settings.storage_local_path)


__all__ = ["StorageBackend", "StoredObjectNotFoundError", "get_storage", "new_storage_key"]
