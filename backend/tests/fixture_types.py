"""Call signatures of the factory fixtures in conftest.py, for annotating test parameters."""

from typing import Protocol

from app.models.user import User


class MakeUser(Protocol):
    async def __call__(self, email: str, role_name: str, password: str = ...) -> User: ...


class AuthHeaders(Protocol):
    async def __call__(self, role_name: str, email: str | None = None) -> dict[str, str]: ...


class StockMatchesLedger(Protocol):
    async def __call__(self, product_id: int) -> None: ...
