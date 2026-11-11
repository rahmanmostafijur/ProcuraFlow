# Vibe96 build: where things stand

Branch `vibe96`, written 2026-11-12 after the final check. The plan is `PLAN.md`. The results of the final check are in
`RELEASE_CHECK.md`; read that first. `NEXT_STEPS.md` is the older deploy checklist for the pre-vibe96 application.

## State

All nine phases are built and committed, one logical step per commit. Nothing is half-done in the working tree.
Left for the owner (out of scope for the build): deploying (Neon, Render, Vercel need the owner's accounts), merging
into `main`, tagging 1.0.0 and the decisions listed in `RELEASE_CHECK.md`.

| Phase | Where |
|---|---|
| 1 company settings, 2 currencies and tax, 3 requests, approvals, budgets, catalog, amendments | `git log --oneline` |
| 4 invoices, receipts, matching, payments, runs; 5 email, PDF, reset and invitations; 6 storage, exports, GDPR, portal | `git log --oneline` |
| 7 design system, every screen redesigned, visual QA | `DESIGN.md`, `DESIGN_REVIEW.md` |
| 8 landing page and demo mode | `backend/app/demo/`, `backend/app/core/demo_guard.py`, `frontend/src/features/landing/` |
| 9 documentation and deployment | `README.md`, `HowToSetup.md`, `deploy/`, `docs/sizing.md` |

## Useful commands

- Demo company: set `DEMO_MODE=true`, then `python -m app.cli.demo_reset` (it empties the database except roles and
  currencies; it refuses to run without `DEMO_MODE`). About 80 seconds.
- Visual QA: `npm run qa:capture` in `frontend/` (needs the demo backend and the dev server; the script refuses to run
  against anything that is not ProcuraFlow). Documentation screenshots: `npm run screenshots`.
- Backend tests need PostgreSQL; the container is `pf-audit-pg` on 127.0.0.1:55432 (see below and `AGENTS.md`).

## Things that bit during the build (worth knowing)

- Run frontend tests from PowerShell with an upper-case drive letter (`D:\ProcuraFlow\frontend`). From Git Bash the
  working directory is `/d/...`, vitest then loads two copies of itself and every file fails with "failed to find the
  current suite".
- Another project's dev server may hold port 5173. Start Vite with `--strictPort` and check the page title; the QA
  scripts do the second part themselves. The demo QA run used backend 8010 and frontend 5180.
- `npm audit fix` can prune `node_modules`; run `npm ci` afterwards.
- Never run two pytest processes at once: they share one test database.
- The GateGuard hook asks for facts before the first Write or Edit to each file, and a config-protection hook blocks
  edits to `eslint.config.js`; satisfy lint in the source, not in the config.

## How to resume

1. `git pull` on `vibe96`, then read `RELEASE_CHECK.md`, `PLAN.md` and this file.
2. Start Docker Desktop. If the test database container is missing:
   `docker run -d --name pf-audit-pg -e POSTGRES_USER=procuraflow -e POSTGRES_PASSWORD=procuraflow -e POSTGRES_DB=procuraflow_test -p 127.0.0.1:55432:5432 postgres:16-alpine`
   (create a second database `procuraflow` in it to run the app).
3. Backend tools are in `backend\.venv\Scripts`; use `127.0.0.1`, not `localhost`. Alembic head is `c4e6a8b0d2f1`.
4. Frontend checks from `frontend/`: `npm run typecheck`, `npm run lint`, `npm run format:check`, `npm test`,
   `npm run build`, `npm run check:contrast`.
5. One commit per step, conventional messages, no tool or vendor attribution anywhere.
