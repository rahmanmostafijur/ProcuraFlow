import ipaddress
from collections.abc import Callable
from typing import Any

FORWARDED_FOR = b"x-forwarded-for"
FORWARDED_PROTO = b"x-forwarded-proto"
SECURE_SCHEMES = {"http": "https", "ws": "wss"}


def _entries(scope: dict[str, Any], header: bytes) -> list[str]:
    """Every comma-separated value across all header lines of one name, in order."""
    values = [value.decode("latin-1") for name, value in scope.get("headers", []) if name == header]
    return [entry.strip() for value in values for entry in value.split(",") if entry.strip()]


def _valid_ip(value: str) -> str | None:
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return None


class TrustedProxyMiddleware:
    """Derive the client address and scheme from `X-Forwarded-*`, trusting exactly `hops` proxies.

    Uvicorn's own proxy handling can only trust addresses, and with a wildcard it takes the
    leftmost `X-Forwarded-For` entry, which the client controls. Render does not publish the
    addresses of its proxy, so this trusts a hop *count* instead:

    * With 0 hops (the default, and local development) the headers are ignored and the client is
      the direct peer.
    * With N hops the chain must have exactly N entries, the leftmost being the client as seen by
      the outermost trusted proxy. A chain of any other length (a spoofed prefix, or a hop count
      that does not match the hosting) resolves to an unknown client rather than a guess. The
      login throttle skips its address check for an unknown client, so a wrong count degrades to
      "per-account limit only" instead of making unrelated users share one address.
    * The scheme comes from the last `X-Forwarded-Proto` value, the one the nearest proxy set.

    This cannot stop a caller who reaches the API directly (not through the trusted proxies) from
    sending a chain of exactly N entries and choosing their own address; only network-level
    restriction of direct access can. That is why the per-account limit is the one to rely on.
    """

    def __init__(self, app: Any, hops: Callable[[], int]) -> None:
        self.app = app
        self._hops = hops

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] in ("http", "websocket"):
            hops = self._hops()
            if hops > 0:
                scope = self._resolve(scope, hops)
        await self.app(scope, receive, send)

    @staticmethod
    def _resolve(scope: dict[str, Any], hops: int) -> dict[str, Any]:
        chain = _entries(scope, FORWARDED_FOR)
        client = _valid_ip(chain[0]) if len(chain) == hops else None

        resolved = {
            **scope,
            "client": (client, 0) if client else None,
            "state": {**scope.get("state", {}), "forwarded_entries": len(chain)},
        }
        protos = _entries(scope, FORWARDED_PROTO)
        if protos and protos[-1].lower() == "https":
            resolved["scheme"] = SECURE_SCHEMES.get(scope.get("scheme", "http"), scope.get("scheme"))
        return resolved
