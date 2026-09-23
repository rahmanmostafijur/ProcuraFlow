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

**Infrastructure:** Docker Compose (PostgreSQL 16, backend, frontend,
Adminer).

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
(`passlib`). The frontend keeps the access token in memory only and the
refresh token in `localStorage`; an axios response interceptor transparently
refreshes an expired access token and retries the original request once.

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
pip install -r requirements.txt
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

## Environment Variables

See `backend/.env.example` and `frontend/.env.example`. Notable ones:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Async Postgres connection string |
| `JWT_SECRET_KEY` | Signing key for access/refresh tokens — **must** be overridden outside local dev |
| `ACCESS_TOKEN_EXPIRE_MINUTES` / `REFRESH_TOKEN_EXPIRE_DAYS` | Token lifetimes |
| `CORS_ORIGINS` | Comma-separated list of allowed frontend origins |
| `DEFAULT_ADMIN_EMAIL` / `DEFAULT_ADMIN_PASSWORD` | Seeded admin credentials |
| `VITE_API_BASE_URL` | Frontend's base URL for the API |

## Testing

Backend (26 tests covering auth, RBAC allow/deny per role, PO state machine
valid/invalid transitions, inventory ledger correctness including the
negative-stock guard, and delivery on-time/delayed classification):

```bash
cd backend
createdb procuraflow_test   # or: docker exec <postgres-container> psql -U procuraflow -c "CREATE DATABASE procuraflow_test;"
pytest
```

Frontend (component and utility unit tests with Vitest + Testing Library):

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

- **Refresh token rotation / revocation list** — refresh tokens are currently
  valid until expiry with no server-side revocation on logout.
- **Frontend code-splitting** — the production bundle is a single ~800KB
  chunk; route-based `React.lazy()` splitting would improve initial load.
- **Dependency upgrades** — `npm audit` flags moderate-severity advisories in
  `vitest`'s mocker and `react-router-dom` 6.x that are fixed in major
  versions not yet adopted here to avoid an unplanned framework migration.
- **Rate limiting** on authentication endpoints.
- **Notifications** — the `notifications` table exists in the schema but
  isn't yet wired to any UI or background trigger (e.g. low-stock alerts).
- **E2E test suite** (Playwright) for the critical flows currently verified
  manually.
