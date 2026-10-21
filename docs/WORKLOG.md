# Work log

Tracks the production-readiness and redesign work. Each task group has a change record in
`docs/changes/` (issue text plus pull-request description), because the GitHub CLI is not signed in on
the development machine; branches are merged locally with `--no-ff` so every group stays one reviewable
unit in history.

Status values: `todo`, `in progress`, `done`, `blocked (owner action)`.

## Baseline (measured 2026-10-22, before any change)

| Check | Result |
|---|---|
| Backend tests | 242 passed (pytest 8.3.4, Postgres 16) |
| Frontend tests | 58 passed in 12 files (Vitest) |
| Production JS bundle | one chunk, 828.40 kB (243.54 kB gzip); CSS 19.31 kB |
| Linters | none configured |

## Section 0: set-up

| Item | Status |
|---|---|
| Repository-local git identity set to the personal address | done |
| Read README, NEXT_STEPS, backend, frontend, tests and migrations | done |
| This work log | done |

## Engineering tasks

| # | Task group | Status | Change record |
|---|---|---|---|
| 1 | CI on GitHub Actions: backend (Postgres 16, migrations, pytest), frontend (typecheck, lint, unit tests, build), e2e, dependency audit; README badges | done (01-ci, awaiting merge) | [01-ci](changes/01-ci.md) |
| 2 | Static checks: ruff (lint + format), mypy (strict where reachable), ESLint (typescript-eslint, react-hooks, jsx-a11y), Prettier; findings fixed; wired into CI | done (02-static-checks, awaiting merge) | [02-static-checks](changes/02-static-checks.md) |
| 3 | Password hashing: passlib replaced by pwdlib (Argon2id), bcrypt hashes verified and rehashed on login; tests | todo | |
| 4 | Repo hygiene: build artifacts removed and ignored, outdated docs fixed, local paths removed, pytest 9 with matching pytest-asyncio | todo | |
| 5 | Low-stock notifications wired to the `notifications` table (same transaction as the ledger row, de-duplicated, unread count, mark as read); tests | todo | |
| 6 | Observability: JSON logs with request ID (also a response header), Prometheus `/metrics` (requests, latency, DB pool), meaningful `/health` and `/ready`; docs | todo | |
| 7 | Migrations as a Render pre-deploy step, `RUN_MIGRATIONS_ON_START=false`; docs | todo | |
| 8 | Route-level code splitting; before and after bundle sizes measured | todo | |
| 9 | Frontend redesign (React 19, Tailwind 4, shadcn/ui, lucide; see section 3 of the brief) | todo | |
| 10 | Playwright end-to-end tests run in CI against Docker Compose | todo | |
| 11 | Demo readiness: read-only Viewer demo account and realistic seed history (only with `SEED_DEMO_DATA=true`) | todo | |
| 12 | Documentation: recruiter README (diagrams, screenshots, decisions), NEXT_STEPS reduced to owner actions | todo | |

## Owner actions

Collected in `NEXT_STEPS.md` under "Owner actions" as they come up.

## Measured results

Filled in as each group is merged.
