# Vibe96 build: where we stopped

Branch `vibe96`, last commit `6418718`, everything pushed, working tree clean (2026-11-01). The plan is `PLAN.md`;
this file is the list of what is left. `NEXT_STEPS.md` is the older deploy checklist for the pre-vibe96 app.

## Done (one commit per step)

| Phase | Commit(s) |
|---|---|
| 1 company settings | 67d356e |
| 2 currencies, tax | 7355dc6 |
| 3 requests, approvals, budgets, catalog, amendments | 1f40c3a |
| 4 invoices, receipts, matching, payments, runs | 8d4e4fa |
| 5 email, PO PDF, reset/invites, notifications | 0110738, a20d83c, d7a4103 (backend), 1f2a442 (frontend) |
| 6 storage, exports, GDPR, supplier docs/bank, payment files, portal | 4d11cba (backend), 6a36e79 (frontend) |
| 7A tokens, themes, fonts, `format.ts` | 785a306 |
| 7 search endpoint for the command palette | 587b785 |
| 7B component library + dev-only `/design-system` | 6418718 |

## Left to do, in order

1. **7C: redesign every screen** (PLAN.md Phase 7, Step C). Details in "Carry-over for 7C" below.
2. **7E: visual QA loop.** Playwright is not installed yet (needs an exact pin). Capture every page at 1440x900,
   1024x768, 390x844, light and dark, into `docs/qa-screens/`; review against the checklist; add axe-core (exact pin)
   to the frontend tests with zero serious/critical violations; log each pass in `DESIGN_REVIEW.md`.
3. **Phase 8: landing page and demo mode.** Landing at `/` (signed-in users go to `/dashboard`), Lighthouse >= 90 on all
   four scores, `DEMO_MODE=true` (one-click role sign-in incl. a supplier, destructive admin actions blocked, email
   logged only, `python -m app.cli.demo_reset`), realistic 12-month seed created through the services, then re-check
   every metric across all screens.
4. **Phase 9: docs and deployment.** README, HowToSetup.md, AGENTS.md (neutral, no attribution), CHANGELOG.md 1.0.0,
   complete `.env.example`, production refuses weak secrets, Docker Compose + Caddy, backup/restore scripts, sizing
   and cost, `docs/metrics.md`, 10+ screenshots at 1920x1080 in `docs/screenshots/`.
5. **Final check, then `RELEASE_CHECK.md` and stop.** All tests, tsc, lint, build, `pip-audit`,
   `npm audit --omit=dev`, attribution scan over every commit on the branch. Also flag the rejected-PO-is-cancelled
   decision and the other "Decisions to review" in PLAN.md.

## Not verified yet (do not skip)

- **The full backend suite has not run since Phase 5** (954 passed then). Phase 6 and the search endpoint were only
  tested file by file (about 190 + 46 new tests plus related files, all passing). Run it once, it takes about an hour:
  `cd backend; $env:TEST_DATABASE_URL="postgresql+asyncpg://procuraflow:procuraflow@127.0.0.1:55432/procuraflow_test"; .venv\Scripts\python.exe -m pytest -q -p no:cacheprovider`
- Nothing in the UI has been looked at in a real browser. All frontend checks so far are jsdom tests, tsc, lint and build.
- Frontend: 392 tests passing at 6418718; backend count is 954 + the Phase 6 and search tests.

## Carry-over for 7C (decisions and gaps the agents reported)

- Existing screens still use `slate-*`, `white` and `brand-NNN` classes. The brand ramp is now emerald, so they
  already look different, but they do not adapt to dark mode. The default theme is therefore `light`; flip
  `DEFAULT_THEME_MODE` in `frontend/src/lib/theme.tsx` to `system` once screens are migrated.
- The app has no `ShortcutProvider` yet (`useShortcut` throws without one), the command palette is not wired to
  `GET /api/v1/search`, and there is no theme toggle UI or notification-centre page beyond the bell. 7C adds them.
- Search results: invoices link to their purchase order (there is no internal invoice page); suppliers link to
  `/suppliers?search=<name>` for users without `supplier:write`. Check the Suppliers page reads `search`.
- No internal invoice page, no payment-run create UI (only list/open/release/cancel/file). The plan's document pages
  (request, PO, invoice, payment run) need the stepper, sticky action bar, summary panel and timeline with comments.
- Supplier detail page takes the name from the first 100 suppliers (no single-supplier endpoint use).
- DateRangePicker takes ISO text, English calendar names. `Badge` (legacy) is untouched; `StatusBadge` is the new one.
- Sidebar badge counts must equal the length of the list they link to (PLAN requirement).
- Theme side-by-side preview can only force dark (no forced-light scope).

## Carry-over for the backend

- Supplier emails carry the PO details but not the PDF (the outbox has no attachments).
- Phase 6 decisions to review: supplier-uploaded invoices are drafts only finance can submit; suppliers see POs from
  `ordered` onwards; PO acknowledgement is not reset by an amendment; account numbers are stored unencrypted;
  supplier documents need `supplier:write` so finance cannot see them; payment files are EUR (SEPA) and USD (NACHA)
  only; the value date is the next weekday; GDPR does not scrub names typed into free-text fields.
- Two StarletteDeprecationWarnings: `HTTP_422_UNPROCESSABLE_ENTITY` should become `HTTP_422_UNPROCESSABLE_CONTENT`.
- zod 3 to 4 and `@hookform/resolvers` 5 upgrade (npm audit advisory) was planned for Phase 7 and is not done.

## How to resume

1. `git pull` on `vibe96`, then read this file and `PLAN.md`.
2. Start Docker Desktop. The test database is the container `pf-audit-pg` (postgres:16-alpine, 127.0.0.1:55432,
   user/password/db `procuraflow`/`procuraflow`/`procuraflow_test`). If it is missing:
   `docker run -d --name pf-audit-pg -e POSTGRES_USER=procuraflow -e POSTGRES_PASSWORD=procuraflow -e POSTGRES_DB=procuraflow_test -p 127.0.0.1:55432:5432 postgres:16-alpine`
3. Backend tools live in `backend\.venv\Scripts` (ruff, mypy, alembic, python). Bare `pytest` is not on the PATH.
   Alembic head is `c4e6a8b0d2f1`. Use `127.0.0.1`, not `localhost` (2 s per connection on this machine).
4. Never run two pytest processes at once: they share one test database.
5. Frontend checks, from `frontend/`: `npx tsc -b`, `npm run lint`, `npx prettier --check .`, `npx vitest run`,
   `npm run build`, `npm run check:contrast`.
6. The GateGuard hook rejects the first Write/Edit to a file until facts are stated; for new files write a one-line
   placeholder first, then the real content. Agents were told the same.
7. Working pattern that worked: one background agent per chunk with a detailed brief, then re-run every check
   yourself before committing with explicit staging. One commit per step, conventional messages, no AI attribution.
