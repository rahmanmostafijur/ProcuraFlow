# RELEASE_CHECK.md: ProcuraFlow 1.0.0

Branch `vibe96`, checked 2026-11-11 and 2026-11-12 on Windows 10 (Docker Desktop, PostgreSQL 16, Python 3.12, Node 22).
This is a record of what was run and what came out, including what failed on the way. It is not a sign-off: the
decisions at the end are the owner's.

## Result in one paragraph

Every automated check is green on the final code: backend 1,280 tests pass in a clean full run (the one run done
under heavy machine load had one failure that did not reproduce, described below), frontend 426 tests pass, both
type-checkers, both linters and both formatters are clean, both dependency audits report nothing, and the attribution
scan found nothing. The user interface was looked at in a real browser for the first time during this check. That
found and fixed real defects, but only 8 of the 204 captured screens were examined by eye. Deployment (Neon, Render,
Vercel, the Docker Compose stack with Caddy) was not exercised.

## Checks and results

### Backend (`backend/`)

| Check | Result |
|---|---|
| `ruff check .` | passed |
| `ruff format --check .` | 309 files already formatted |
| `mypy` (strict) | no issues in 309 source files |
| Full test suite, run 1 (while Playwright, Vite and the demo backend ran on the same machine) | 1,245 passed, 19 failed in 2 h 00 min |
| Full test suite, run 2 (quiet machine, code as of commit `3c0110f`) | **1,280 passed, 0 failed**, 1 h 28 min |
| The eight test files that exercise the later hardening (auth, refresh rotation, demo mode, demo seed, config, deploy readiness, GDPR, seed), on the final backend code | **191 passed, 0 failed** |
| `pip-audit -r requirements.txt` | no known vulnerabilities |

The 19 failures of run 1:

- 18 in `tests/test_invoice_permissions.py`. The test loops every role through the invoice endpoints; the `supplier`
  role (added in phase 6) is stopped earlier, with "Supplier accounts can only use the portal", which is intended
  behaviour. The test was wrong, not the code. It now loops staff roles only and has a separate test that every guarded
  endpoint refuses a supplier account with that message.
- 1 in `tests/test_demo_seed.py::test_the_reset_removes_what_visitors_added`: the seed was answered with a 401 midway.
  It passed on its own (three times), in suite order after every earlier test file (435 passed), and in run 2. I could
  not reproduce it and do not know the cause. The machine was heavily loaded by my own browser runs at the time, so
  interference is the likeliest explanation, but that is a guess. If it shows up again in CI, look at it first.

After run 2, three backend changes were made in response to a security review of demo mode (below). They are covered
by tests in `tests/test_demo_mode.py`; the backend files that exercise those modules were run again, not the whole suite.

### Frontend (`frontend/`)

| Check | Result |
|---|---|
| `npm run typecheck` | clean |
| `npm run lint` | clean |
| `npm run format:check` | clean |
| `npm test` | 71 files, 426 tests passed (417 before this check; the additions are axe, contrast and month-format tests) |
| `npm run build` | passed; entry chunk 306 kB (492 kB before lazy loading) |
| `npm run check:contrast` | all 56 token pairings meet WCAG AA, light and dark |
| `npm audit --omit=dev` | 0 vulnerabilities |

Frontend tests must be run from PowerShell with an upper-case drive letter; from Git Bash every file fails to load
(see `HANDOFF.md`).

### Attribution scan

Commit messages of every commit reachable in the repository, and every tracked file except the lockfile and the
captured images, searched for `co-authored-by`, `generated with`, vendor and assistant names: no matches.

## Verified in a browser (Chromium via Playwright, against the demo seed)

- Every page, 34 of them (landing, sign-in, forgot password, every internal page including the detail pages, and the
  four supplier-portal pages) at 1440x900, 1024x768 and 390x844, light and dark: 204 captures. The final run has no
  serious or critical axe violation, no horizontal overflow and no console error. `DESIGN_REVIEW.md` lists each
  pass and the defects fixed (dark-mode contrast of the logo tile, light-only status badges, unnamed controls, scroll
  regions without keyboard access, ISO month labels).
- Looked at by a person (me) in full: dashboard (three variants), landing page, purchase order (desktop and phone),
  invoice, supplier list on a phone, company settings in dark mode, and the sign-in, payment runs and supplier-portal
  screenshots. **The other captures were judged by the automated checks only.**
- Lighthouse 12 on the landing page of the production build (served by `vite preview`, mobile profile, one run):
  performance 94, accessibility 100, best practices 100, SEO 100. Before the fixes it was 81 / 100 / 96 / 91.
- Business numbers against the seed: 34 comparisons all agree (see below).
- 17 documentation screenshots at 1920x1080 in `docs/screenshots/`, referenced from `README.md`.

### Business numbers

A script (not committed; it lived in a scratch folder) signed in as the demo roles, read each figure from every screen's
API and compared it with an independent query written from `docs/metrics.md` against the seeded database:

- Orders: dashboard total, pending and completed equal the order list and the SQL counts (46 / 6 / 40).
- Active suppliers, inventory value ($32,673.70), low-stock products and upcoming deliveries equal SQL.
- Committed spend by month (all 12 months, bucketed in the company time zone), spend by supplier and the SQL total are
  the same amount; order counts agree between the month series, the supplier report and SQL.
- Payables outstanding and overdue equal SQL and equal the invoice list totals; invoices needing attention agree on
  the dashboard, the list and SQL.
- All six budgets (spent, committed, remaining, utilisation, health), including one over budget (112.1%).
- The sidebar approvals badge equals the length of the approvals list for seven roles, and the bell's unread count
  equals the unread notifications in its list.

34 of 34 matched. This reproduces the existing backend consistency tests against live demo data; it does not replace
them. The five figures that `docs/metrics.md` lists as computed outside `metrics_service.py` were not covered.

### Review by independent readers

Three read-only reviews ran against the finished work (demo-mode security, the frontend changes, documentation
against code). Fixed as a result: user creation is blocked in demo mode; a demo account's refresh cookie stops working
when demo mode is off; the loading fallback for lazy routes is centred; capture scripts write relative to the
repository; stale documentation (demo mode described as planned, wrong section references, a backend example
environment file missing settings). The rest is under "Known limits".

## What was not verified

- **Deployment.** Neon, Render and Vercel were not touched. The Docker Compose stack with Caddy and its automatic
  HTTPS, and the backup and restore scripts, were not run. `HowToSetup.md` describes them from reading the files.
- **Real email.** SMTP delivery was never tried against a mail server; in the demo and in tests email is logged only.
- **S3-compatible storage** is covered by tests against a fake, not against a real service.
- **Other browsers and devices.** Only Chromium, only emulated viewports. No Firefox, Safari, real phone or screen reader.
- **Lighthouse** ran once, locally, without the compression and caching headers Caddy or Vercel will add; scores vary
  by a few points from run to run.
- Playwright and the number script are not part of CI.
- The five figures outside `metrics_service.py` and the CSV exports were not re-checked against the seed.
- 196 of the 204 captured screens were not examined by a person.

## Known limits

- Purchase order lines show a product id, not a name, because the order item response carries only `product_id`
  (needs an additive response field and a screen change).
- Dashboard recent activity prints the raw action ("Avery Quinn login").
- On a phone the lifecycle stepper stacks vertically and its connector renders as a short bar; wide tables scroll
  sideways inside their card instead of becoming cards.
- The sign-in page's left brand panel is mostly empty; `PLAN.md` Step C mentions "a small live component" there.
- A number field that is left blank is accepted as 0 where 0 is allowed (unit price, cost, minimum stock, payment
  terms, lead time, tolerance). zod 3 behaved the same; the upgrade did not change it.
- No error boundary for a failed chunk load: after a deploy, a browser tab that still holds the old page can show a
  blank screen until it is reloaded. Sign-in and the shell now load on demand, so this path matters more than before.
- The portal shell has no loading boundary of its own around its pages (existing behaviour).
- Demo mode: `python -m app.cli.demo_reset` deletes every table except roles, permissions and currencies, and the only
  protection against pointing it at a real database is `DEMO_MODE` being off. In production the application refuses
  `DEMO_MODE=true` without `ALLOW_DEMO_IN_PRODUCTION=true`, but in development and staging there is no further check.
  The command also prints the shared demo password to its log. The demo guard is a list of blocked requests, so a new
  route that changes users is open until a rule is added; a request body that cannot be parsed skips the body-based
  rules (the framework rejects such a body anyway).
- Product costs, stock and numbering are per installation (one company); there is no multi-tenancy.
- A vite dev server on another project's port makes screenshots of the wrong app; the scripts now detect that.
- The brand colour is validated as six-digit hex for the logo tile only; other surfaces use whatever the settings hold.

## Decisions to review

These are the owner's to make. None was changed.

From `PLAN.md`:

1. **A rejected purchase order ends as `cancelled`**, with the reason kept, because the order lifecycle has no way back
   to draft and adding a `submitted -> draft` transition would change the core state machine. Rejected purchase
   requests can be edited and resubmitted. Say if you want orders to return to draft instead.
2. Approval rules are seeded only with the demo data. A fresh install keeps single-step approval until an admin adds
   rules, so upgrading an existing installation changes nothing by surprise.
3. SMTP credentials live in environment variables, not the database; the settings page shows whether SMTP is
   configured and can send a test message.
4. The role and permission matrix is defined in code (the seed re-applies it), so the roles screen is read-only.
5. Anonymising a user also redacts that user's name and email inside audit entries about them; the entries stay.

From `HANDOFF.md` (phase 6 and 5):

6. Supplier-uploaded invoices are drafts that only finance can submit.
7. Suppliers see purchase orders from `ordered` onwards; a PO acknowledgement is not reset by an amendment.
8. Bank account numbers are stored unencrypted.
9. Supplier documents need `supplier:write`, so the finance role cannot see them.
10. Payment files cover EUR (SEPA) and USD (NACHA) only; the value date is the next weekday.
11. GDPR anonymisation does not scrub names typed into free-text fields.
12. Supplier emails carry the purchase order details but not the PDF (the outbox has no attachments).

New in this check:

13. **Demo mode signs visitors in without a password** by design. Whether the public demo should exist at all, and where it
    is hosted, is your call; keep it on a deployment with no real data.
14. Whether `demo_reset` should demand an explicit confirmation (for example the database name) before it empties
    anything, given the blast radius described above.
15. The 1.0.0 tag and release date; `CHANGELOG.md` still says the date is set when this check passes.
