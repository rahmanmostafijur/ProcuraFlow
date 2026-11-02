# Production frontend image: build the static bundle, then serve it with Caddy.
# Build context is ./frontend (see deploy/docker-compose.yml); the Caddyfile is read from ../deploy.
#
# Verify the pinned tags before the first build with `docker pull`; bump them deliberately, not by accident.

# --- build stage -------------------------------------------------------------------------------------------------
FROM node:22.11.0-alpine AS build
WORKDIR /app

# Exact lockfile install: the build is reproducible and fails if package.json and the lockfile disagree.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
# VITE_API_BASE_URL is intentionally unset: production builds call the same-origin /api/v1 that Caddy proxies.
RUN npm run build

# --- runtime stage -----------------------------------------------------------------------------------------------
FROM caddy:2.8.4-alpine

# Run Caddy as an unprivileged user. Ports 80 and 443 are still allowed through the file capability that the
# official image sets on the caddy binary.
RUN addgroup -S caddy && adduser -S -G caddy -H -s /sbin/nologin caddy \
    && mkdir -p /data /config /srv \
    && chown -R caddy:caddy /data /config /srv

COPY --from=build --chown=caddy:caddy /app/dist /srv
# "deploy" is a named build context that points at the deploy/ directory (additional_contexts in
# deploy/docker-compose.yml). Building this file without it fails on the next line; use docker compose.
COPY --from=deploy Caddyfile /etc/caddy/Caddyfile

USER caddy
EXPOSE 80 443 443/udp
CMD ["caddy", "run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
