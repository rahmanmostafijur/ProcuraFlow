import logging

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.core.config import get_settings
from app.core.proxy import TrustedProxyMiddleware
from app.main import app
from app.models.login_failure import LoginFailure

DIRECT_PEER = "10.0.0.5"


async def _echo(request):
    return JSONResponse(
        {
            "client": request.client.host if request.client else None,
            "scheme": request.url.scheme,
            "entries": getattr(request.state, "forwarded_entries", None),
        }
    )


async def _call(hops: int, headers: dict[str, str] | list[tuple[str, str]]) -> dict:
    wrapped = TrustedProxyMiddleware(Starlette(routes=[Route("/", _echo)]), hops=lambda: hops)
    transport = ASGITransport(app=wrapped, client=(DIRECT_PEER, 4321))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return (await client.get("/", headers=headers)).json()


async def test_forwarded_headers_are_ignored_when_no_proxy_is_trusted():
    seen = await _call(0, {"X-Forwarded-For": "6.6.6.6", "X-Forwarded-Proto": "https"})

    assert seen["client"] == DIRECT_PEER
    assert seen["scheme"] == "http"


async def test_the_client_is_the_forwarded_entry_when_the_chain_has_exactly_the_trusted_hops():
    seen = await _call(2, {"X-Forwarded-For": "203.0.113.9, 198.51.100.4"})

    assert seen["client"] == "203.0.113.9"
    assert seen["entries"] == 2


async def test_a_single_trusted_hop_uses_the_single_entry():
    assert (await _call(1, {"X-Forwarded-For": "203.0.113.9"}))["client"] == "203.0.113.9"


@pytest.mark.parametrize(
    "chain",
    [
        "6.6.6.6, 203.0.113.9, 198.51.100.4",  # a spoofed prefix makes the chain longer than the trusted hops
        "203.0.113.9",  # shorter: a proxy did not append what we expected
        "",
    ],
)
async def test_a_chain_of_the_wrong_length_is_not_trusted_and_the_client_is_unknown(chain: str):
    headers = {"X-Forwarded-For": chain} if chain else {}

    assert (await _call(2, headers))["client"] is None


@pytest.mark.parametrize("entry", ["not-an-ip", "999.1.1.1", "203.0.113.9:8080", "<script>"])
async def test_an_entry_that_is_not_an_ip_address_is_rejected(entry: str):
    assert (await _call(1, {"X-Forwarded-For": entry}))["client"] is None


async def test_ipv6_addresses_are_normalised_so_one_client_has_one_key():
    seen = await _call(1, {"X-Forwarded-For": "2001:0DB8:0:0:0:0:0:1"})

    assert seen["client"] == "2001:db8::1"


async def test_repeated_header_lines_are_read_as_one_chain():
    seen = await _call(2, [("X-Forwarded-For", "203.0.113.9"), ("X-Forwarded-For", "198.51.100.4")])

    assert seen["client"] == "203.0.113.9"


@pytest.mark.parametrize(
    "proto, expected",
    [("https", "https"), ("http, https", "https"), ("https, http", "http"), (None, "http")],
)
async def test_https_is_detected_from_the_nearest_proxy_only(proto: str | None, expected: str):
    headers = {"X-Forwarded-For": "203.0.113.9"}
    if proto:
        headers["X-Forwarded-Proto"] = proto

    assert (await _call(1, headers))["scheme"] == expected


@pytest.fixture
def two_trusted_hops(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "trusted_proxy_hops", 2)


async def _wrong_login(client: AsyncClient, email: str, chain: str | None):
    headers = {"X-Forwarded-For": chain} if chain else {}
    return await client.post("/api/v1/auth/login", json={"email": email, "password": "wrong"}, headers=headers)


async def test_clients_behind_the_proxy_are_throttled_individually(client: AsyncClient, roles, two_trusted_hops):
    for index in range(20):
        assert (await _wrong_login(client, f"ghost{index}@example.com", "1.1.1.1, 9.9.9.9")).status_code == 401

    blocked = await _wrong_login(client, "new@example.com", "1.1.1.1, 9.9.9.9")
    other_client = await _wrong_login(client, "new@example.com", "2.2.2.2, 9.9.9.9")

    assert blocked.status_code == 429
    assert other_client.status_code == 401


async def test_a_spoofed_chain_never_creates_an_address_key_or_an_address_block(
    client: AsyncClient, roles, two_trusted_hops, db_session: AsyncSession
):
    for index in range(25):
        spoofed = f"10.0.0.{index}, 1.1.1.1, 9.9.9.9"
        assert (await _wrong_login(client, f"ghost{index}@example.com", spoofed)).status_code == 401

    db_session.expire_all()
    ip_rows = await db_session.scalar(select(func.count()).select_from(LoginFailure).where(LoginFailure.scope == "ip"))
    assert ip_rows == 0


async def test_forwarded_headers_cannot_dodge_the_address_limit_when_no_proxy_is_trusted(
    client: AsyncClient, roles
):
    for index in range(20):
        assert (await _wrong_login(client, f"ghost{index}@example.com", f"7.7.7.{index}")).status_code == 401

    assert (await _wrong_login(client, "new@example.com", "8.8.8.8")).status_code == 429


async def test_a_failed_sign_in_logs_the_resolved_client_address_for_verifying_the_proxy_setup(
    client: AsyncClient, roles, two_trusted_hops, caplog: pytest.LogCaptureFixture
):
    with caplog.at_level(logging.WARNING):
        await _wrong_login(client, "someone@example.com", "203.0.113.50, 198.51.100.4")

    messages = [record.getMessage() for record in caplog.records]
    assert any("client_ip=203.0.113.50" in message and "forwarded_entries=2" in message for message in messages)
    assert not any("someone@example.com" in message for message in messages)
