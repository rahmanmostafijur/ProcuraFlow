# ProcuraFlow

A B2B procurement, inventory, and delivery management platform for small and
medium sized businesses. ProcuraFlow tracks the full purchasing lifecycle —
from supplier and product catalog management, through purchase order approval
workflows, to inventory receiving and delivery performance reporting — behind
role-based access control and a full audit trail.

## Problem Statement

Small and mid-sized businesses that buy physical goods from multiple suppliers
tend to manage purchasing in spreadsheets and email threads: purchase orders
with no enforced approval process, inventory counts that drift from reality
because stock changes aren't tracked consistently, and no way to answer "which
suppliers deliver on time?" or "what did we spend last month?" without manual
reconciliation. ProcuraFlow centralizes that workflow behind a single
application with enforced business rules, a real audit trail, and live
analytics computed from actual transactional data.

## Features

- **Dashboard** — purchase order counts by state, inventory value, low-stock
  alerts, upcoming deliveries, a monthly purchasing trend chart, and a live
  recent-activity feed — all computed from the database, not hardcoded.
- **Supplier management** — CRUD, active/inactive status, search, sort, and
  pagination.
- **Product catalog** — SKU, category, unit, cost, stock thresholds, supplier
  linkage, low-stock filtering.
- **Purchase orders** — a full state machine
  (`draft → submitted → approved → ordered → partially_received → received`,
  with `cancelled` reachable from any pre-received state), enforced
  server-side with a guarded transition table. Multi-line-item orders with a
  dynamic item builder in the UI.
- **Inventory** — every stock change (manual adjustment or PO receipt) is
  recorded as an append-only ledger entry (`inventory_transactions`); the
  product's `current_stock` is only ever mutated alongside a ledger row in the
  same DB transaction.
- **Deliveries** — auto-created when a PO is marked ordered; tracks expected
  vs. actual date and computes on-time/delayed/partial status from real
  receiving data.
- **Reports** — supplier performance (spend and order count), delayed
  deliveries with variance in days, on-time delivery rate, and a CSV export of
  current inventory status.
- **Audit log** — every mutating action (login, supplier/product changes, PO
  transitions, inventory adjustments, user management) is recorded with actor,
  entity, and a JSON payload of relevant details.
- **RBAC** — five roles (Admin, Procurement Manager, Purchasing Officer,
  Warehouse Manager, Viewer) with a data-driven permission matrix, enforced on
  every mutating endpoint server-side. The frontend also hides actions the
  current user can't perform, but that's a UX convenience — the API rejects
  unauthorized requests regardless of what the client sends.

## Architecture

```
React (Vite, TypeScript)
        │  REST + JWT
        ▼
FastAPI routers  →  Pydantic schemas (request/response validation)
        │
        ▼
Service layer (business logic: PO state machine, inventory ledger, delivery calc)
        │
        ▼
SQLAlchemy 2.0 (async ORM)
        │
        ▼
PostgreSQL 16
```

Each layer has one job. Routers handle HTTP concerns (auth, status codes,
pagination params) and delegate business rules to the service layer, which is
the only place that mutates domain state — this is what makes the PO state
machine and inventory ledger enforceable and testable independent of the web
framework.

## Technology Stack

**Backend:** Python, FastAPI, SQLAlchemy 2.0 (async, `asyncpg`), Pydantic v2,
Alembic, PyJWT, passlib/bcrypt, pytest + pytest-asyncio + httpx.

**Frontend:** React 18, TypeScript, Vite, Tailwind CSS, TanStack Query, React
Router v6, React Hook Form + Zod, Recharts, Vitest + Testing Library.

**Infrastructure:** Docker Compose for local development (PostgreSQL 16,
backend, frontend, Adminer); a production container image, Render blueprint
and Vercel config for deployment (see [Deployment](#deployment)).

## Database Architecture

Normalized PostgreSQL schema, managed entirely through Alembic migrations
(`backend/alembic/versions/`) — the schema is reproducible from an empty
database via `alembic upgrade head`.

| Table | Purpose |
|---|---|
| `users`, `roles`, `permissions`, `role_permissions` | Auth and a data-driven RBAC matrix (roles map to permission codes, not hardcoded checks) |
| `suppliers` | Supplier records with active/inactive status |
| `categories`, `products` | Product catalog with stock thresholds and cost, `CHECK` constraints preventing negative stock/cost |
| `purchase_orders`, `purchase_order_items` | Orders and line items; status is a Postgres enum with server-enforced transitions |
| `inventory_transactions` | Append-only stock movement ledger (manual adjustment or PO receipt) |
| `deliveries` | Auto-created per ordered PO; tracks expected/actual dates and computed status |
| `audit_logs` | Append-only record of every significant action, with a JSONB payload |
| `notifications` | Per-user notification records |

Indexes exist on every foreign key, plus `products.sku`,
`purchase_orders.status`/`po_number`, `inventory_transactions.product_id`, and
`audit_logs.entity_type`/`entity_id` — the columns actually filtered or
joined on in the query patterns above.

## Authentication

JWT access tokens (30 min) + refresh tokens (7 days), issued from
`POST /api/v1/auth/login`. Passwords are hashed with bcrypt
(`passlib`). The frontend keeps the access token in memory only. The refresh
token is an `HttpOnly`, `SameSite=Lax` cookie (`Secure` outside local
development) scoped to `/api/v1/auth`, so page scripts can never read it and
browsers don't send it on cross-site POSTs. Refresh tokens rotate: each
`POST /api/v1/auth/refresh` marks the presented token used and issues one
successor from the same login (`refresh_tokens` table: random token id, family
id, expiry, used/revoked timestamps). React StrictMode or two tabs can
legitimately send the same cookie twice at once, so a used token presented
again within a 10-second grace window still gets a fresh access token but **no
new refresh token**: the first request already minted the one successor, which
the browser stores, so a replay can never start a second live chain. A used
token presented after the window is treated as stolen: its whole login family
is revoked and a `refresh_token_reuse` event is written to the audit log
before the 401 is returned. `POST /api/v1/auth/logout` revokes the session
server-side (whichever token of the chain is presented) and clears the cookie,
leaving the user's other devices signed in. Changing a user's password or
deactivating them revokes all of that user's sessions in the same transaction
(audited as `user_sessions_revoked`), so a stolen refresh token does not
survive a password reset and a reactivated account does not revive old logins;
`PATCH /api/v1/users/{id}` is the only credential-change path today, so a
future self-service change or reset endpoint must call `revoke_all_sessions`.
Tokens issued before rotation existed, or with no stored row, are rejected.
An axios response interceptor transparently refreshes an expired access
token and retries the original request once. The only thing in `localStorage`
is a non-secret flag that tells the app whether a session probably exists.

### Sign-in throttling

Failed logins are counted per account (the dependable control) and per client
address (a weaker second layer against spraying many accounts). Past the limit,
`POST /api/v1/auth/login` answers `429` with a `Retry-After` header — even for
the correct password — until the window passes; a successful login clears that
account's count. Known limits: the counters live in the API process, so they
reset on restart and are not shared across instances (a scaled-out deployment
would need a shared store such as Redis); the client address is taken from
`X-Forwarded-For`, which a caller can spoof, which is why the per-account limit
is the one to rely on; and locking an account lets someone else keep a known
email locked out for the window.

## Authorization (RBAC)

Permissions are rows in the database (`permissions` table), assigned to roles
via `role_permissions`. A FastAPI dependency,
`require_permission("supplier:write")`, loads the current user's role and
permission codes and returns `403` if the required code isn't present — see
`backend/app/core/deps.py` and `backend/app/core/permissions.py` for the full
matrix. This means authorization is never a hardcoded `if role == "admin"`
check scattered across routers; it's centralized and testable
(`backend/tests/test_rbac.py`).

## API Documentation

Interactive OpenAPI docs are served by FastAPI at `/docs` (Swagger UI) and
`/redoc` once the backend is running. All endpoints live under `/api/v1`.

## Local Setup

### Prerequisites

- Python 3.12+
- Node.js 20+
- PostgreSQL 16 (or use Docker — see below)

### Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate   # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements-dev.txt   # runtime + test dependencies
cp .env.example .env     # adjust DATABASE_URL if not using the default port
alembic upgrade head
python -m app.seeds.seed
uvicorn app.main:app --reload
```

The API is now at `http://localhost:8000`, with docs at
`http://localhost:8000/docs`.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

The app is now at `http://localhost:5173`.

### Default login (from the seed script)

- Email: whatever `DEFAULT_ADMIN_EMAIL` resolves to (see `.env.example`)
- Password: whatever `DEFAULT_ADMIN_PASSWORD` resolves to

**Change these in production** — they're seeded from environment variables
specifically so the defaults are never hardcoded into the app.

## Docker Setup

```bash
docker compose up -d --build
```

This starts Postgres, runs migrations and the seed script, and brings up the
backend (`:8000`) and frontend (`:5173`), plus Adminer (`:8080`) for
inspecting the database. Postgres itself is exposed on host port `5433` (not
the default `5432`) to avoid colliding with a locally installed PostgreSQL
instance — the services talk to each other over the Docker network on the
standard port regardless.

> **Windows/macOS note:** the frontend's Vite dev server uses polling for its
> file watcher (`vite.config.ts`) because Docker's bind-mounted filesystem on
> those platforms doesn't emit native change events that Vite's default
> watcher relies on.

## Deployment

Target: **Neon** (PostgreSQL) + **Render** (API container) + **Vercel**
(static frontend). Vercel proxies `/api/*` to Render, so the browser only ever
talks to one origin — no CORS configuration and no third-party-cookie problems.

1. **Database (Neon).** Create a project and copy its connection string. Either
   the direct or the `-pooler` host works: provider-style URLs
   (`postgresql://…?sslmode=require&channel_binding=require`) are rewritten for
   asyncpg automatically, and the statement cache is disabled behind a pooler.
2. **API (Render).** New → Blueprint, pointing at this repo (`render.yaml`).
   When prompted, set `DATABASE_URL`, `DEFAULT_ADMIN_EMAIL` and
   `DEFAULT_ADMIN_PASSWORD` (unique, 12+ characters). `JWT_SECRET_KEY` is
   generated for you. On every start the container runs `alembic upgrade head`,
   seeds roles/permissions and the first admin, then serves; the app refuses to
   boot in production with a placeholder or short JWT secret. `render.yaml`
   also sets `SEED_DEMO_DATA=true` so the public demo gets sample suppliers and
   products; delete that variable for a real deployment, which then receives
   only the roles, permissions and first admin.
3. **Frontend (Vercel).** Import the repo with **Root Directory** `frontend`
   (the Vite preset is detected). Before deploying, edit the `destination` in
   `frontend/vercel.json` to your Render service URL. No environment variables
   are needed.
4. **Verify.** Work through [Post-deployment verification](#post-deployment-verification).

Render's free tier sleeps after 15 minutes idle and takes about a minute to
wake. The login page handles this: it polls `/api/ready` for up to 100 seconds,
explains the cold start with a progress bar after 3 seconds, treats Render's
HTML placeholder page and 502/503/504 as "still waking", and shows an error
with a **Try again** button if the server never answers. Sign-in is enabled
only once the database is reachable.

### Post-deployment verification

None of these has been run against a real Render, Neon or Vercel environment
yet; the automated tests cover the logic behind each one, not the hosting.

1. `https://<render-service>/health` and `/api/ready` return 200, and so does
   `https://<vercel-app>/api/ready` (proves the rewrite).
2. After 15+ minutes idle, the login page shows the waking notice after about
   3 seconds and enables sign-in once ready; it never spins forever.
3. After signing in, DevTools shows a `refresh_token` cookie that is `HttpOnly`,
   `Secure`, `SameSite=Lax`, path `/api/v1/auth`, on the Vercel domain. The
   login response body contains no refresh token, and `localStorage` holds only
   `procuraflow_has_session`.
4. A hard reload keeps you signed in (`POST /api/v1/auth/refresh` 200, then
   `/auth/me`), and the cookie value changes on each reload (rotation).
5. Reloading two tabs at once, or firing two refreshes from the console, gives
   200 for both and keeps you signed in; only one response sets a cookie.
6. Reuse: copy the cookie, wait over 10 seconds, let the app refresh, then
   `curl -X POST https://<vercel-app>/api/v1/auth/refresh --cookie "refresh_token=<old>"`
   returns 401 and the app is signed out at its next refresh; an admin sees
   `refresh_token_reuse` in the audit log.
7. Logout clears the cookie and a later refresh returns 401, while a second
   browser stays signed in. Changing that user's password (as admin) signs the
   second browser out too.
8. On a throwaway account (not the admin), five wrong passwords produce a 429
   with a minutes message, and the right password is refused for 15 minutes.
9. A deep link such as `/suppliers` loads the app, security headers are present
   (`curl -I`), and Reports → Export Inventory CSV downloads a file.
10. Render's logs show the migrations reaching the latest revision, and
    `refresh_tokens` exists in Neon.

### Security notes

- The interactive API docs (`/docs`, `/openapi.json`) stay public on the Render
  host so reviewers can read them; Vercel only forwards `/api/*`.
- No `Content-Security-Policy` is set. The SPA's charts need inline styles, and
  a policy cannot be validated without a browser, so a wrong one would risk a
  blank page. `X-Frame-Options`, `nosniff`, HSTS, `Referrer-Policy` and
  `Permissions-Policy` are set in `frontend/vercel.json`.
- Uvicorn trusts `X-Forwarded-*` from any peer (`--forwarded-allow-ips='*'`).
  That is only safe because the container is reachable solely through the
  platform's proxy; do not expose it directly.
- The seed re-syncs each role's permissions from `app/core/permissions.py` on
  every start, so permission edits made directly in the database are
  overwritten by design.
- Report endpoints, including the CSV export, are available to any signed-in
  user, like the other read endpoints; changing that means changing the RBAC
  matrix.
- Migrations run on every start, which is correct for one instance. A
  scaled-out deployment needs a pre-deploy migration step instead.

To build and run the production image locally:

```bash
docker build -t procuraflow-api backend
docker run --rm -p 8000:8000 -e ENVIRONMENT=production \
  -e DATABASE_URL=postgresql://user:pass@host/db \
  -e JWT_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')" \
  -e DEFAULT_ADMIN_EMAIL=admin@example.com -e DEFAULT_ADMIN_PASSWORD='a-unique-12+char-password' \
  procuraflow-api
```

## Environment Variables

See `backend/.env.example` and `frontend/.env.example`. Notable ones:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Async Postgres connection string |
| `JWT_SECRET_KEY` | Signing key for access/refresh tokens — **must** be overridden outside local dev |
| `ACCESS_TOKEN_EXPIRE_MINUTES` / `REFRESH_TOKEN_EXPIRE_DAYS` | Token lifetimes |
| `LOGIN_MAX_FAILURES_PER_ACCOUNT` / `LOGIN_MAX_FAILURES_PER_IP` / `LOGIN_LOCKOUT_SECONDS` | Sign-in throttling: failures tolerated per account (default 5) and per client address (20) within the window (900 s) |
| `CORS_ORIGINS` | Comma-separated list of allowed frontend origins. Unset: local origins in development/test, none in production |
| `DEFAULT_ADMIN_EMAIL` / `DEFAULT_ADMIN_PASSWORD` | Seeded admin credentials (a unique password of 12+ characters is enforced outside local dev) |
| `SEED_ON_START` | Production container only: `false` skips the seed step on boot (default `true`) |
| `SEED_DEMO_DATA` | Seed sample suppliers/products. Unset: yes in development/test, no in staging/production; `render.yaml` sets it for the public demo |
| `PORT` | Production container only: listen port (set by the host; default `8000`) |
| `VITE_API_BASE_URL` | Frontend's base URL for the API. Unset in production builds, which use same-origin `/api/v1` |

## Testing

Backend (204 tests covering auth, refresh-token rotation and revocation,
sign-in throttling, RBAC allow/deny per role, PO state machine valid/invalid
transitions, inventory ledger correctness including the negative-stock guard,
delivery on-time/delayed classification, the audit trail, seed safety, and a
migration upgrade/downgrade/upgrade round trip on a fresh database):

```bash
cd backend
createdb procuraflow_test   # or: docker exec <postgres-container> psql -U procuraflow -c "CREATE DATABASE procuraflow_test;"
pytest
```

Frontend (56 component, utility, session and cold-start tests with Vitest +
Testing Library; `npm run build` also type-checks):

```bash
cd frontend
npm test
```

## Screenshots

_Add screenshots of the dashboard, purchase order detail view, and reports
page here before sharing this project publicly._

## Future Improvements

Honest list of things a production deployment would need that this portfolio
build doesn't include:

- **Absolute session lifetime** — refresh tokens rotate, but each refresh
  starts a fresh 7-day window, so an actively used session never expires on
  its own.
- **Access tokens are short-lived, not revocable** — after logout or a
  password change, an access token already issued keeps working until it
  expires (30 minutes), and a token replayed inside the 10-second grace window
  yields one such access token. Deactivated users are cut off immediately,
  because every request re-checks the account.
- **Frontend code-splitting** — the production bundle is a single ~800KB
  chunk; route-based `React.lazy()` splitting would improve initial load.
- **Dependency advisories** — `npm audit --omit=dev` reports two moderate
  advisories in `react-router` 6.x, in its server-side-rendering hydration
  code. This is a client-rendered SPA with no server rendering, so that path
  is not reachable; the fix needs the breaking v7 upgrade. Dev-only advisories
  (vitest's mocker) are not shipped. The Python dependencies have not been
  scanned.
- **Notifications** — the `notifications` table exists in the schema but
  isn't yet wired to any UI or background trigger (e.g. low-stock alerts).
- **E2E test suite** (Playwright) for the critical flows currently verified
  manually.
