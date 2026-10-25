import asyncio
from pathlib import Path

from app.storage.base import StoredObjectNotFoundError, validate_storage_key


class LocalStorage:
    """Files on the local disk under one root directory (a mounted volume in containers)."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        path = (self._root / validate_storage_key(key)).resolve()
        # The key pattern already rules out "..", but resolve-and-compare also covers symlinks inside the root.
        if not path.is_relative_to(self._root):
            raise StoredObjectNotFoundError(key)
        return path

    async def save(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)

        def _write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

        await asyncio.to_thread(_write)

    async def read(self, key: str) -> bytes:
        path = self._path(key)
        try:
            return await asyncio.to_thread(path.read_bytes)
        except FileNotFoundError as exc:
            raise StoredObjectNotFoundError(key) from exc

    async def delete(self, key: str) -> None:
        path = self._path(key)
        await asyncio.to_thread(path.unlink, missing_ok=True)
