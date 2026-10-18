from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ASYNCPG_SCHEME = "postgresql+asyncpg"
PLAIN_POSTGRES_SCHEMES = frozenset({"postgres", "postgresql"})
# libpq-only parameters that asyncpg rejects as unknown connect arguments.
UNSUPPORTED_QUERY_PARAMS = frozenset({"channel_binding"})
POOLER_HOST_MARKER = "-pooler"


def normalize_database_url(url: str) -> str:
    """Turn a provider-issued Postgres URL into one SQLAlchemy's asyncpg driver accepts.

    Providers such as Neon hand out `postgresql://...?sslmode=require&channel_binding=require`,
    which is libpq syntax: asyncpg wants the `postgresql+asyncpg` scheme and `ssl=` instead.
    """
    parts = urlsplit(url)
    scheme = ASYNCPG_SCHEME if parts.scheme in PLAIN_POSTGRES_SCHEMES else parts.scheme

    query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if key in UNSUPPORTED_QUERY_PARAMS:
            continue
        query.append(("ssl" if key == "sslmode" else key, value))

    return urlunsplit((scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def uses_connection_pooler(url: str) -> bool:
    """True for pooled endpoints (Neon's `-pooler` hosts), which sit behind PgBouncer."""
    host = urlsplit(url).hostname or ""
    return POOLER_HOST_MARKER in host


def asyncpg_connect_args(url: str) -> dict[str, int]:
    """Driver arguments for `url`.

    PgBouncer in transaction mode hands each statement a different server connection, so
    asyncpg's server-side prepared statements break ("prepared statement ... does not exist").
    Disabling its statement cache is the documented fix.
    """
    return {"statement_cache_size": 0} if uses_connection_pooler(url) else {}
