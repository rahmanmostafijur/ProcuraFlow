"""The seed's way into the application: the real HTTP API, called in-process as one of the demo users.

Going through the API means every document passes the same validation, permissions, approval engine, budget and
matching rules as a person using the screens, so totals, approvals, matching and stock agree by construction.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token

API = "/api/v1"
BASE_URL = "http://demo.internal"
SUCCESS = (200, 201, 202, 204)


class DemoSeedError(RuntimeError):
    """A request the seed expected to succeed was refused; the message names it and the server's answer."""


class DemoApi:
    def __init__(self, client: AsyncClient) -> None:
        self._client = client
        self._people: dict[str, tuple[int, str]] = {}

    def register(self, key: str, user_id: int, role_name: str) -> None:
        """Make ``key`` an actor the seed can act as (a demo account key)."""
        self._people[key] = (user_id, role_name)

    def user_id(self, key: str) -> int:
        return self._people[key][0]

    def _headers(self, actor: str) -> dict[str, str]:
        user_id, role_name = self._people[actor]
        return {"Authorization": f"Bearer {create_access_token(str(user_id), role_name)}"}

    async def call(
        self,
        actor: str,
        method: str,
        path: str,
        *,
        json: Any = None,
        data: dict[str, str] | None = None,
        files: dict[str, tuple[str, bytes, str]] | None = None,
        params: dict[str, Any] | None = None,
        expect: tuple[int, ...] = SUCCESS,
    ) -> Any:
        response = await self._client.request(
            method, f"{API}{path}", json=json, data=data, files=files, params=params, headers=self._headers(actor)
        )
        if response.status_code not in expect:
            raise DemoSeedError(f"{actor} {method} {path} -> {response.status_code}: {response.text[:500]}")
        return response.json() if response.content else None

    async def get(self, actor: str, path: str, **kwargs: Any) -> Any:
        return await self.call(actor, "GET", path, **kwargs)

    async def post(self, actor: str, path: str, body: Any = None, **kwargs: Any) -> Any:
        return await self.call(actor, "POST", path, json=body, **kwargs)

    async def put(self, actor: str, path: str, body: Any = None, **kwargs: Any) -> Any:
        return await self.call(actor, "PUT", path, json=body, **kwargs)

    async def patch(self, actor: str, path: str, body: Any = None, **kwargs: Any) -> Any:
        return await self.call(actor, "PATCH", path, json=body, **kwargs)


@asynccontextmanager
async def open_demo_api() -> AsyncIterator[DemoApi]:
    # Imported here: the application imports the demo package (for the demo sign-in routes), not the other way round.
    from app.main import app  # noqa: PLC0415

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        yield DemoApi(client)
