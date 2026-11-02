# AGENTS.md

Build, test and convention guide for automated coding tools and human contributors working in this repository.
`PLAN.md` holds the product plan, `HANDOFF.md` the current state of the work, `docs/metrics.md` the definition of every
business number.

## Layout

```
backend/            FastAPI application (Python 3.12)
  app/core/         settings, security, permissions, money, fiscal-year and clock helpers
  app/models/       SQLAlchemy 2 models
  app/schemas/      Pydantic request and response models
  app/routers/      HTTP layer: authentication, permission checks, thin handlers
  app/services/     business rules and transactions (the only place state changes)
  app/storage/      file storage interface (local disk, S3-compatible)
  app/seeds/        roles, permissions, first admin, optional demo data
  app/cli/          jobs run from cron (daily jobs, email delivery)
  alembic/          migrations
  tests/            pytest suite (needs PostgreSQL)
frontend/           React 18, TypeScript, Vite, Tailwind 3 (src/, scripts/)
deploy/             Docker Compose, Caddyfile, backup and restore scripts
docs/               metrics, sizing, screenshots, change records
```

Layering is routers -> services -> models. Routers stay thin; rules live in services, split by domain, kept under
about 350 lines per file.

## Commands

Backend (run from `backend/`; the virtual environment is `.venv`):

```bash
python -m venv .venv
. .venv/bin/activate                  # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
ruff check .
ruff format --check .
mypy                                  # strict, configured in pyproject.toml
alembic upgrade head
python -m app.seeds.seed
uvicorn app.main:app --reload
```

Backend tests need a disposable PostgreSQL database. They create and drop tables, so never point
`TEST_DATABASE_URL` at real data:

```bash
export TEST_DATABASE_URL=postgresql+asyncpg://procuraflow:procuraflow@127.0.0.1:5432/procuraflow_test
python -m pytest -q
```

Run one pytest process at a time: all runs share the one test database. Use `127.0.0.1`, not `localhost`, in database
URLs (on some Windows hosts `localhost` costs about two seconds per connection). The full suite is long; run the
files you touched first, then the whole suite before a release.

Frontend (run from `frontend/`):

```bash
npm ci
npm run dev
npm run typecheck        # tsc -b
npm run lint
npm run format:check
npm test                 # vitest run
npm run build
npm run check:contrast   # design-token contrast check
```

Dependency audits: `pip-audit -r backend/requirements.txt` and `npm audit --omit=dev` (from `frontend/`).

## Rules

- **Money is `Decimal`.** Python uses `Decimal`, PostgreSQL uses `Numeric`; never `float` for an amount. Rounding is
  owned by `app/core/money.py`: per line, `ROUND_HALF_UP`, to the currency's minor units. The API carries amounts as
  decimal strings.
- **One definition per metric.** Business numbers are computed only in `app/services/metrics_service.py` and documented
  in `docs/metrics.md`. A new figure gets a function there, a row in the document and a consistency test.
- **Every endpoint is authenticated and permission-checked.** Reads are scope-checked: a record outside the caller's
  scope answers 404, not 403, so identifiers cannot be probed. Permission codes and role grants live in
  `app/core/permissions.py`; the seed re-applies them on start.
- **Every write is audited**, and approvals keep separation of duties (nobody approves their own document).
- **Migrations only add or widen.** New tables, nullable or defaulted columns with backfills, wider numeric types. Each
  migration has a working downgrade covered by the round-trip test. Anything destructive needs an explicit decision.
- **No secrets in the repository.** Configuration comes from the environment (`.env.example` lists every setting).
  Production refuses placeholder or short secrets; do not weaken those checks.
- **Dependencies are pinned exactly** in `requirements*.txt` and `package.json`. Add a library only where the standard
  library or an existing dependency will not do, and run the audits after adding one.
- **Spreadsheet export safety.** Anything written to CSV goes through the shared writer that neutralises formulas.
- **Tests with every change.** Each feature gets tests for the happy path, permission denied, validation, scope (an
  identifier belonging to someone else) and edge cases. Fix the code, not the test, unless the test is wrong.
- **Time zones.** Calendar periods use the company time zone from settings, never the server's or the browser's.
- **Frontend formatting.** Money and dates are formatted with `Intl` through `src/lib/format.ts`, never by hand;
  amounts and table figures use tabular numerals; colours come from design tokens, not raw palette classes.

## Workflow

- One logical step per commit, with a conventional message (`feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`,
  `perf:`, `ci:`) that says what changed and why.
- Before committing: backend `ruff check`, `ruff format --check`, `mypy` and the relevant tests; frontend `typecheck`,
  `lint`, `format:check`, `test` and `build`. Stage files explicitly; do not stage generated output such as
  `frontend/dist/` or `*.tsbuildinfo`.
- Do not change the domain model or a state machine without agreeing it first (for example, purchase order statuses
  and their allowed transitions are enforced in `app/services/purchase_order_service.py`).
- Keep `README.md`, `HowToSetup.md`, `.env.example`, `CHANGELOG.md` and `docs/metrics.md` in step with the code they
  describe.
- Commit messages, pull requests and documents describe the change only; they carry no tool or vendor attribution.

## Pointers

- Run locally: `HowToSetup.md`. Deploy: `HowToSetup.md` and `deploy/`.
- Container start-up (migrate, seed, serve): `backend/start.sh`.
- Health endpoints: `/health` (bare), `/api/health`, `/api/ready` (database reachable).
- API reference when the backend runs: `/docs` and `/redoc`.
