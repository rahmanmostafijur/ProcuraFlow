# ProcuraFlow

[![CI](https://github.com/rahmanmostafijur/ProcuraFlow/actions/workflows/ci.yml/badge.svg)](https://github.com/rahmanmostafijur/ProcuraFlow/actions/workflows/ci.yml)
[![Dependency audit](https://github.com/rahmanmostafijur/ProcuraFlow/actions/workflows/audit.yml/badge.svg)](https://github.com/rahmanmostafijur/ProcuraFlow/actions/workflows/audit.yml)

A lean, self-hosted procure-to-pay application for small and mid-size companies. ProcuraFlow takes a purchase from the
first request, through approval, ordering, receiving and the supplier's invoice, to payment, with role-based access,
an audit trail on every write and numbers that agree on every screen.

It runs as one installation for one company: your server, your database, your data. The plan positions it as a
one-time licence with no monthly fee and full source code (see [Licence](#licence)).

## Contents

[Features](#features) - [Architecture](#architecture) - [Technology stack](#technology-stack) -
[Quick start](#quick-start) - [Configuration](#configuration) - [Screenshots](#screenshots) -
[Security](#security) - [Testing](#testing) - [Documentation](#documentation) - [Licence](#licence)

## Features

**Buying**
- Purchase requests by any employee, with approval rules by document type and amount band, ordered approval steps,
  delegation while away, per-user approval limits and separation of duties (nobody approves their own document).
- Conversion of an approved request into one draft purchase order per chosen supplier.
- Purchase orders with a guarded state machine (`draft`, `submitted`, `approved`, `ordered`, `partially_received`,
  `received`, `cancelled`), multi-currency totals, per-line tax, branded PDF, amendments with versions and a readable diff.
- Budgets per cost centre and fiscal year (spent, committed, remaining), optional blocking of over-budget approvals,
  warnings at a set percentage, transfers with approval and history.
- Catalog items with contract price, supplier and lead time.

**Receiving and paying**
- Goods receipts with accepted and rejected quantities, returns to supplier, an append-only inventory ledger and
  delivery tracking (on time, delayed, partial).
- Supplier invoices matched two-way (price) and three-way (price and received quantity), duplicate detection,
  exceptions routed through the approval rules, manual and partial payments.
- Payment runs that a second person must release, with SEPA (EUR) and NACHA/ACH (USD) payment files.

**Suppliers**
- Supplier records, documents with expiry tracking (valid, expiring soon, expired), bank details changed only with a
  second approver, and a lite supplier portal where invited suppliers see only their own orders, acknowledge them,
  upload invoices and keep their documents current.

**Control and compliance**
- Single company settings: currencies, exchange rates, tax rates, fiscal year, time zone, number prefixes, tolerances.
- Roles: admin, procurement manager, purchasing officer, warehouse manager, finance, department manager, employee,
  viewer, and a supplier account for the portal. Permissions are data (`app/core/permissions.py`), not scattered checks.
- Audit log, GDPR export and anonymisation that keep financial records intact, accounting CSV exports (QuickBooks Online
  and Xero bill layouts), email outbox with editable templates, notification centre.

**Numbers you can trust**
- One service computes every business figure; the dashboard, reports and badges call the same functions and tests prove
  they agree. See [docs/metrics.md](docs/metrics.md).

Features of the landing page and the one-click demo mode belong to phase 8 of [PLAN.md](PLAN.md); check
[HANDOFF.md](HANDOFF.md) and [CHANGELOG.md](CHANGELOG.md) for whether they are in the build you are running.

## Architecture

```mermaid
flowchart LR
    Browser["Browser<br/>React 18 SPA"] -->|"HTTPS"| Caddy["Caddy<br/>static files, TLS, /api proxy"]
    Caddy -->|"/api/*"| API["FastAPI<br/>routers, services"]
    API --> DB[("PostgreSQL 16")]
    API --> Files["File storage<br/>local volume or S3-compatible"]
    API -->|"SMTP (optional)"| Mail["Mail server"]
    Cron["cron: daily jobs,<br/>email retry, backups"] --> API
    Cron --> DB
```

Inside the API each layer has one job:

```mermaid
flowchart TD
    R["Routers: HTTP, authentication, permission and scope checks"] --> S["Services: business rules, transactions, metrics"]
    S --> M["SQLAlchemy 2 async models"]
    M --> P[("PostgreSQL")]
    S --> St["Storage interface"]
    S --> E["Email outbox"]
```

Routers handle HTTP and delegate to services, the only place that changes business state. A record outside the
caller's scope answers 404, so identifiers cannot be probed.

## Technology stack

| Layer | Technology |
|---|---|
| API | Python 3.12, FastAPI, async SQLAlchemy 2 with asyncpg, Pydantic v2, Alembic, PyJWT, passlib/bcrypt, ReportLab, Pillow, Jinja2 (sandboxed email templates) |
| Database | PostgreSQL 16 (money as `Numeric`, `Decimal` in code) |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS 3 with design tokens, TanStack Query, React Router, React Hook Form with Zod, Recharts |
| Tests and checks | pytest, pytest-asyncio, httpx; Vitest and Testing Library; ruff, strict mypy, ESLint, Prettier, `tsc` |
| Deployment | Docker Compose with Caddy (automatic HTTPS), or Render + Neon + Vercel |

Exact versions are pinned in `backend/requirements.txt` and `frontend/package.json`.

## Quick start

Prerequisites: Python 3.12, Node.js 20 or newer (CI uses 22), PostgreSQL 16 (or Docker). Full instructions for
Windows, macOS and Linux are in [HowToSetup.md](HowToSetup.md).

```bash
# 1. Database (skip if you already run PostgreSQL 16)
docker run -d --name procuraflow-db -e POSTGRES_USER=procuraflow -e POSTGRES_PASSWORD=procuraflow \
  -e POSTGRES_DB=procuraflow -p 127.0.0.1:5432:5432 postgres:16-alpine

# 2. Backend
cd backend
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp ../.env.example .env                           # development defaults work as they are
alembic upgrade head
python -m app.seeds.seed                          # roles, permissions, first admin, sample data
uvicorn app.main:app --reload                     # http://localhost:8000, docs at /docs

# 3. Frontend, in a second terminal
cd frontend
npm ci
npm run dev                                       # http://localhost:5173
```

Sign in with the admin email and password from your `.env` (`DEFAULT_ADMIN_EMAIL`, `DEFAULT_ADMIN_PASSWORD`). The
placeholder password is accepted only in development and test.

Production with Docker Compose and Caddy, in short:

```bash
cp .env.example .env     # set SITE_ADDRESS, JWT_SECRET_KEY, POSTGRES_PASSWORD, admin email and password
docker compose --env-file .env -f deploy/docker-compose.yml up -d --build
```

The step-by-step version, backups, upgrades and troubleshooting are in [HowToSetup.md](HowToSetup.md).

## Configuration

Every setting is listed, with comments and safe placeholders, in [.env.example](.env.example). The rules that matter:

- `ENVIRONMENT` defaults to `production`. In production and staging the API **refuses to start** with a placeholder,
  short or repetitive `JWT_SECRET_KEY` (under 32 characters or fewer than 10 different ones), with a missing, default
  or very short database password, or with `DEMO_MODE=true` unless `ALLOW_DEMO_IN_PRODUCTION=true` is also set; the
  seed refuses a default or short (under 12 characters) admin password.
- Never commit a real `.env`. Generate secrets with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
- Demo sample data (`SEED_DEMO_DATA`) is for demonstrations; a real installation does not need it.

## Screenshots

Screenshots are captured by a script at 1920x1080 and stored in `docs/screenshots/`. They are added when the
documentation phase is finished; the folder is empty until then. Planned set (file names are the intended ones, not
yet present):

| Screen | File |
|---|---|
| Landing page | `docs/screenshots/landing.png` |
| Dashboard | `docs/screenshots/dashboard.png` |
| Purchase request and approvals | `docs/screenshots/requests.png`, `docs/screenshots/approvals.png` |
| Purchase order | `docs/screenshots/purchase-order.png` |
| Supplier invoice with matching | `docs/screenshots/invoice.png` |
| Payment run | `docs/screenshots/payment-run.png` |
| Budgets | `docs/screenshots/budgets.png` |
| Reports | `docs/screenshots/reports.png` |
| Supplier portal | `docs/screenshots/supplier-portal.png` |
| Settings | `docs/screenshots/settings.png` |

Once the images exist, reference them here with `![Dashboard](docs/screenshots/dashboard.png)`.

## Security

- Short-lived access tokens held in memory only; rotating refresh tokens in an `HttpOnly`, `SameSite=Lax` cookie
  (`Secure` outside development) scoped to `/api/v1/auth`. Reuse of a used refresh token after a short grace window
  revokes the whole login family and is audited. A session never outlives `SESSION_ABSOLUTE_DAYS` (default 30).
- Sign-in throttling per account and per client address, stored in PostgreSQL so it survives restarts and is shared
  by every instance; the answer is `429` with `Retry-After`. Keys are HMAC hashes, so typed emails are not stored.
- Forwarded headers are trusted only by hop count (`TRUSTED_PROXY_HOPS`), never by wildcard.
- Role and permission checks on every endpoint, record-level scope checks that answer 404, supplier portal isolation
  enforced in one scoped query layer, an audit log on every write, spreadsheet-formula neutralisation in CSV exports,
  upload validation by content signature, and a strict Content-Security-Policy on the served frontend.
- Known limits are listed in [PLAN.md](PLAN.md) ("Decisions to review"), [HANDOFF.md](HANDOFF.md) and
  [NEXT_STEPS.md](NEXT_STEPS.md): access tokens already issued stay valid until they expire (30 minutes by default)
  after logout; someone who knows an account's email can keep it locked for the lockout window; account numbers in
  supplier bank details are stored unencrypted.

Report a vulnerability privately to the repository owner rather than in a public issue.

## Testing

```bash
# Backend (needs a disposable PostgreSQL database; never use real data)
cd backend
export TEST_DATABASE_URL=postgresql+asyncpg://procuraflow:procuraflow@127.0.0.1:5432/procuraflow_test
python -m pytest -q
ruff check . && ruff format --check . && mypy

# Frontend
cd frontend
npm test && npm run typecheck && npm run lint && npm run format:check && npm run build
```

The suites cover authentication and refresh-token rotation, the sign-in throttle, proxy-header trust, permissions per
role, scope (identifier) checks, the purchase order and invoice state machines, matching, budgets, payment runs and
files, the supplier portal's isolation, the metrics consistency tests, and a migration upgrade, downgrade and upgrade
round trip. Test counts change with every phase; run the suites for current numbers rather than trusting a figure
written here. CI ([.github/workflows/ci.yml](.github/workflows/ci.yml)) runs lint, types, migrations, tests and the
frontend build on every push and pull request.

## Documentation

| File | Content |
|---|---|
| [HowToSetup.md](HowToSetup.md) | Local development, configuration, database, production deployment, backups, upgrades, troubleshooting |
| [.env.example](.env.example) | Every setting with comments and safe placeholders |
| [docs/metrics.md](docs/metrics.md) | Definition, formula, source tables and screens for every number |
| [docs/sizing.md](docs/sizing.md) | Server sizing, monthly cost ranges, storage growth |
| [AGENTS.md](AGENTS.md) | Build, test and convention guide for contributors and automated tools |
| [CHANGELOG.md](CHANGELOG.md) | Release notes |
| [PLAN.md](PLAN.md), [HANDOFF.md](HANDOFF.md), [NEXT_STEPS.md](NEXT_STEPS.md) | Plan, current state and older deployment checklist |

## Licence

The plan describes a one-time licence with source code included, but **no `LICENSE` file exists in this repository
yet**, so no licence is granted by this repository as it stands. Add the licence text you intend to ship before
distributing the code, and update this section to match. All design, text and names in the project are original.
