#!/bin/sh
# Production entrypoint: migrate, bootstrap, then serve.
# Hosts without a pre-deploy hook (e.g. Render's free tier) run this as the start command.
set -eu

alembic upgrade head

# Creates the roles/permissions and the first admin; both are idempotent. Demo catalogue data is
# only inserted into an empty database. Set SEED_ON_START=false once the first admin exists.
if [ "${SEED_ON_START:-true}" = "true" ]; then
    python -m app.seeds.seed
fi

# Behind a platform proxy, trust X-Forwarded-* so request URLs and client IPs are the real ones.
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --proxy-headers \
    --forwarded-allow-ips='*'
