#!/bin/sh
# Production entrypoint: migrate, bootstrap, then serve.
# Hosts without a pre-deploy hook (e.g. Render's free tier) run this as the start command.
set -eu

# A scaled-out deployment runs `alembic upgrade head` once as a pre-deploy step and sets this to false.
# With one instance the default is right; concurrent starters are safe either way (advisory lock).
if [ "${RUN_MIGRATIONS_ON_START:-true}" = "true" ]; then
    alembic upgrade head
fi

# Creates the roles/permissions and the first admin; both are idempotent. Demo catalogue data is
# only inserted into an empty database. Set SEED_ON_START=false once the first admin exists.
if [ "${SEED_ON_START:-true}" = "true" ]; then
    python -m app.seeds.seed
fi

# Uvicorn's own proxy handling is off: with a wildcard it would take the client-controlled leftmost
# X-Forwarded-For entry. The app trusts exactly TRUSTED_PROXY_HOPS proxies itself (app/core/proxy.py).
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --no-proxy-headers
