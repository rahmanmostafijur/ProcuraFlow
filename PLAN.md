# ProcuraFlow 1.0 plan

Goal: turn ProcuraFlow into a complete, self-hosted procure-to-pay product for small and mid-size companies in the
US and Europe. Work happens on the `vibe96` branch, one phase at a time, one conventional commit per phase after
backend tests, frontend tests, type-check, lint and build are green. Nothing is pushed or deployed.

Positioning: a lean, self-hosted procure-to-pay app for small and mid-size companies in the US and Europe with a
one-time licence, no monthly fee, full source code and numbers you can trust. All design, text, names and layouts are
original; nothing is copied from another product.

Out of scope for v1.0: AI assistant, contracts module, third-party ERP integrations, e-signature, guided product tour,
Arabic/RTL.

## Starting point (measured 2026-10-26 on `main` at 06d6cfe)

- Backend: FastAPI, async SQLAlchemy 2, Alembic, Postgres 16. 242 tests pass, ruff and strict mypy are clean.
- Frontend: React 18, TypeScript, Vite 6, Tailwind 3, TanStack Query. 58 tests pass, ESLint and `tsc` are clean.
- Layering: routers (HTTP, permissions) -> services (rules, transactions) -> models. Permission codes and role
  grants live in `app/core/permissions.py`; the seed re-applies them on every start.
- Security behaviour kept as is: JWT access tokens plus rotated refresh tokens in an httpOnly cookie, Postgres-backed
  login throttle, 30-day absolute session cap, separation of duties on approvals, audit log on every write,
  CSV formula-injection protection, trusted-proxy hop counting, strict CSP on the frontend host.
- Single company per installation (no tenants). "Scope" therefore means record-level rules inside one company:
  an employee sees their own requests, invoices are visible only to finance roles, attachments inherit the
  visibility of their parent record.

This brief supersedes the open items 3 to 12 of `docs/WORKLOG.md` (that list wanted React 19, Tailwind 4 and
shadcn/ui; this brief keeps Tailwind 3 with a token-based design system). The work log gets a pointer to this file.

## Conventions for all phases

- Money: `Decimal` in Python, `Numeric` in Postgres. `app/core/money.py` owns rounding: per line, `ROUND_HALF_UP`,
  to the currency's minor units. Unit prices keep 4 decimals; amounts are stored with 4 decimals of scale and
  always hold values already rounded to the currency.
- Every new endpoint: authenticated, permission-checked, and reads are scope-checked (a record outside the caller's
  scope answers 404, so ids cannot be probed). Each feature gets tests for the happy path, permission denied,
  validation, scope (IDOR) and edge cases.
- Migrations only add or widen: new tables, nullable or defaulted columns with backfills, wider numeric types.
  Each has a working downgrade, and the existing round-trip test covers it. Anything destructive stops for a decision.
- Business logic in services, split by domain so no file passes ~350 lines. Routers stay thin.
- Dependencies pinned exactly (backend already is; frontend loses every `^`/`~`). New libraries only where the
  standard library will not do: `python-multipart` (uploads), `reportlab` + `pillow` (PDF, image checks),
  `jinja2` (sandboxed email templates), `boto3` (optional S3 storage), `@fontsource/plus-jakarta-sans`,
  `@playwright/test` (screenshots). Each is checked with `pip-audit` / `npm audit` when added.

## Phase 1: company settings

- `company_settings` singleton (one row, enforced by a check constraint): company and legal name, address,
  tax/VAT id, logo, brand colour, base currency, fiscal-year start month, date format, timezone, PO number prefix,
  invoice tolerance %, default payment terms (days).
- New permission `settings:manage` (admin). Any signed-in user reads settings; a public `/settings/branding`
  endpoint (name, colour, logo URL) feeds the sign-in page.
- File storage interface (`app/storage/`) with a local-disk backend; the logo is its first user (PNG/JPEG,
  size-limited, content checked with Pillow, served with `nosniff`).
- PO numbers use the configured prefix. Frontend: settings page, branding provider for header and sign-in page,
  dates and money formatted from settings. Housekeeping: pin frontend versions, stop tracking build artifacts.

## Phase 2: currencies and tax

- `currencies` (ISO 4217 code, symbol, minor units, active) with a standard list loaded by the migration;
  `exchange_rates` (rate to the base currency, effective date, kept per base currency) maintained by hand.
- `tax_rates` (name, %, VAT or sales tax, inclusive/exclusive, reverse charge, active) with editable seeded examples:
  sample US state sales tax, UK 20%, DE 19%, FR 20%, NL 21%, EU reverse charge 0%.
- Purchase orders gain currency, per-line tax (rate snapshot on the line so editing a rate never rewrites history),
  stored subtotal / tax total / grand total, and at approval the exchange rate plus base-currency totals. Existing
  orders are backfilled in the base currency with rate 1. Suppliers gain default currency, country, VAT number and
  payment terms. New permission `finance:manage`, new role `finance`.
- Dashboard and reports switch to stored base-currency amounts. Base currency can only change while no order has a
  locked rate.
- Metrics integrity (the core selling point) starts here: `app/services/metrics_service.py` is the only place a
  business number is computed, one definition per metric, documented in `docs/metrics.md` (name, formula, period,
  timezone, statuses included). The dashboard and every report call it. "This month" uses the company time zone.
  Each later phase adds its metrics to the same service and the same document, and a cross-screen test asserts that
  every metric is identical through every API that shows it.

## Phase 3: purchase requests and approval rules

- `purchase_requests` + lines (free-text description, optional catalogue product, quantity, estimated price,
  suggested supplier), notes and attachments. Any employee creates them; they see only their own unless they hold
  `request:read_all` or are an approver on that request.
- Conversion of an approved request into one draft PO per chosen supplier; lines remember the PO they went to.
- `approval_rules` per document type (request, PO, invoice exception) by base-currency amount band, each with
  ordered steps naming an approver role. On submit the matching rule's steps are copied onto the document, so
  later rule edits do not affect documents in flight. With no matching rule, one step open to holders of the
  type's approve permission keeps today's single-approval behaviour.
- Delegation while away (date range, revocable). Nobody approves their own document or two steps of the same
  document. Every decision, including "on behalf of", is audited.
- One state-machine extension: a rejected PO returns from `submitted` to `draft` for correction. Everything else in
  the PO lifecycle stays as it is. The existing `/purchase-orders/{id}/approve` endpoint keeps working by deciding
  the current step.
- "My approvals" queue for requests, POs and (Phase 4) invoice exceptions. New roles: `employee`,
  `department_manager`. Generic `attachments` table (parent type + id) with access derived from the parent.
- Per-user approval limits by document type (base currency): a user cannot decide a document above their limit.
  Delegation for a date range records both the delegate and the original approver on every decision.
- Budgets per cost centre and fiscal year (the fiscal year start comes from settings): spent, committed, remaining,
  computed by the metrics service. Settings: block over-budget requests (on/off) and warn the owner at a configurable
  percentage. Moving budget between cost centres needs finance approval and keeps a full change history. A request or
  PO that breaks a blocking rule cannot be approved, checked in the service so no endpoint can skip it (tested).
  POs and requests carry a cost centre.
- Simple catalog: items with contract price, supplier and lead time; request lines can pick from it.
- PO amendments: an ordered PO can be amended, each change creates a version with a readable diff of what changed
  (lines, prices, dates, supplier terms), and an amendment that raises the total goes back through approval.

## Phase 4: supplier invoices, matching and payments

- `supplier_invoices` + lines against PO lines, attachment for the PDF/image, duplicate check on supplier +
  invoice number, due date from payment terms.
- Two-way (price) and three-way (price + received quantity, cumulative across invoices) matching using the
  settings tolerance. Mismatches are stored as reasons and become `exception`, which goes through the approval rules.
- Statuses: draft, matched, exception, approved, on hold, paid, void. Manual payments (bank transfer, card, cheque),
  partial payments allowed, never above the open amount; fully paid invoices become `paid`.
- Permissions `invoice:read`, `invoice:write`, `invoice:approve`, `payment:write`.
- Goods receipt with accepted and rejected quantity and a condition note. Rejected quantity stays open on the PO, and
  three-way matching counts accepted quantity only. A lightweight return-to-supplier record has a reason, a resolution
  (replace, credit note or repair) and a status.
- Duplicate invoice detection (same supplier and invoice number, or same supplier, amount and a date within a
  window) is stored as a match exception with a link to the invoice it duplicates.
- Payment runs: approved invoices are grouped into a run that a second person must release; the same person cannot
  create and release it. Releasing records the payments. File export of a released run is in Phase 6.

## Phase 5: documents and email

- Branded PO PDF (ReportLab): logo, company and supplier addresses, lines, tax breakdown per rate, totals in the PO
  currency, payment terms.
- `email_outbox` (every message with status, attempts, last error) written in the business transaction and
  delivered afterwards over SMTP (stdlib `smtplib`, settings from the environment). Development and demo mode log
  instead of sending. A CLI retries queued messages.
- Editable `email_templates` (invitation, password reset, approval needed, PO to supplier, invoice exception),
  rendered in a Jinja2 sandbox with a fixed variable list and validated on save.
- Password reset and invitations: hashed, single-use tokens (reset: 30 minutes), throttled requests, no account
  enumeration, sessions revoked on reset. Profile page: change own password.
- Notification centre on the existing `notifications` table, with a command that runs daily (for cron) to create
  notifications for expiring supplier documents (Phase 6) and overdue approvals.

## Phase 6: attachments, exports and GDPR

- S3-compatible storage backend (optional, selected by environment). Upload validation by content signature and
  size; downloads only for users who can see the parent record.
- Accounting CSVs: bills in QuickBooks Online and in Xero import layouts, plus POs, invoices and suppliers, all
  through one shared writer that applies the existing formula-injection protection.
- GDPR (`gdpr:manage`, admin): JSON export of a user's or supplier contact's personal data; anonymisation that keeps
  financial records intact; both recorded in the audit log.
- Supplier documents (W-9, VAT certificate, insurance, ISO, bank letter) with expiry dates. The status (valid,
  expiring soon, expired) is computed from today's date when queried and never stored. Changing a supplier's bank
  details needs a second approver, and the old details stay in the history.
- Payment file export from a released payment run: SEPA credit transfer (ISO 20022 pain.001) for EU suppliers and
  NACHA/ACH CSV for US suppliers; the file is generated once per run and the export is audited.
- Lite supplier portal: suppliers are invited by email and sign in to a separate, simpler area (own role, own routes).
  They see only their own POs, acknowledge them, upload invoices and keep their documents current. Isolation is
  enforced in a single scoped query layer and tested hard: a supplier can never read or change another supplier's
  data, and a supplier account can reach no internal endpoint.

## Phase 7: design system and redesign

- Step A, `DESIGN.md` first: brand idea in one sentence; tokens as CSS variables wired into `tailwind.config.ts`
  (ink/navy neutrals 50-950, emerald/teal brand, amber accent, red/orange/blue for status, each text pairing checked
  against WCAG AA, light and dark themes, spacing scale, radii 8/12/16/20, three soft layered elevations, motion
  durations and easing, `prefers-reduced-motion` honoured). Plus Jakarta Sans self-hosted via `@fontsource`, tabular
  numerals on every amount, table and KPI, a mono face only for document numbers, negative letter-spacing on display
  sizes. Money and dates formatted with `Intl` from the company locale and currency, never hand-built strings.
- Step B, component library with a dev-only `/design-system` route showing every component in every state (default,
  hover, focus, disabled, loading, error, empty, dark): buttons, inputs, selects, combobox, date range picker, data
  table (sorting, filters, column visibility, pagination, row selection, sticky header, density toggle), status
  badges, KPI cards with sparkline, token-themed charts with custom tooltips, modal, drawer, tabs, toasts, skeletons,
  empty states with original SVG illustrations in one style, confirm dialog, command palette (Ctrl+K, recent items
  and actions, backed by a scope-aware `/search` endpoint), shortcut help (?), lifecycle stepper, activity timeline,
  diff viewer, file dropzone.
- Step C, every screen redesigned: collapsible sidebar grouped by workflow with badges, breadcrumbs, global search,
  theme toggle, notification centre, user menu. Every document page (request, PO, invoice, payment run) has a
  lifecycle stepper, a sticky action bar with only the permitted actions, a summary panel and an activity timeline
  with comments. Optimistic updates with rollback, inline validation, unsaved-changes warning. Split sign-in with a
  small live component in the brand panel. Dashboard: request-to-paid pipeline strip, KPI cards with sparklines, spend
  by month, budget health by cost centre, "waiting for you", documents expiring soon. Responsive to 360px, keyboard
  accessible, routes code-split. Sidebar badge counts equal the length of the list they link to.
- Step E, visual QA loop: a Playwright script captures every page at 1440x900, 1024x768 and 390x844 in light and dark
  into `docs/qa-screens/`; the screenshots are reviewed against the checklist (spacing, overflow, hierarchy with one
  primary action per view, icon sizes, right-aligned tabular amounts, empty and loading states, focus rings, dark-mode
  contrast) and fixed until clean. axe-core checks in the frontend tests allow zero serious or critical violations.
  `DESIGN_REVIEW.md` logs each pass.

## Phase 8: landing page and demo mode

- Step D, public landing page at `/` (signed-in users go to `/dashboard`): hero about trustworthy numbers and no
  monthly fee with an animated request-to-pay pipeline built from real app components and realistic data (not
  screenshots); the problem today, how it works, feature grid, "numbers you can trust" (metrics integrity explained),
  security (audit log, RBAC, token rotation, throttling, supplier isolation), self-hosted with a one-time licence, FAQ
  and a call to action to the live demo. No fake testimonials, customer logos or invented statistics. Lighthouse on
  the landing page: Performance, Accessibility, Best Practices and SEO all at least 90.
- `DEMO_MODE=true`: one-click role sign-in on the login page (including a supplier), destructive admin actions
  blocked, email logged only, and `python -m app.cli.demo_reset` restores the demo data (for a nightly cron).
- Realistic seed for a fictional US/EU company across 12 months in USD, EUR and GBP, created through the services
  so totals, approvals, matching and stock all agree. It also shows every later feature alive: budgets near and over
  limit, an expired and an expiring supplier document, a duplicate-invoice exception, a partial receipt with a
  rejection and a return, a PO with two amendments, a delegated approval, a released SEPA run and two invited
  suppliers with portal accounts. Afterwards every metric is re-checked across all screens.

## Phase 9: documentation and deployment

- README, HowToSetup.md, AGENTS.md, CHANGELOG.md (1.0.0), complete `.env.example`; production refuses weak secrets.
- Docker Compose route with Caddy (automatic HTTPS) and database backup/restore scripts; the existing Render + Neon +
  Vercel route; sizing and monthly cost for both.
- README, HowToSetup.md, AGENTS.md, CHANGELOG.md, `.env.example` and `docs/metrics.md` brought up to date.
- Playwright script that captures at least 10 screenshots at 1920x1080 into `docs/screenshots/`, including the
  landing page and the supplier portal.

## Final check

All tests, type-check, lint, build, `pip-audit`, `npm audit --omit=dev`, an attribution scan over every commit on the
branch, then `RELEASE_CHECK.md`. Stop and wait.

## Decisions to review

1. Rejected POs end as `cancelled` with the reason kept, because the order lifecycle has no way back to draft and adding a
   `submitted -> draft` transition would change the core state machine. Rejected purchase requests can be edited and
   resubmitted (they are a new document type). Say if you want orders to return to draft instead.
2. Approval rules are seeded only with demo data. A fresh install keeps single-step approval until an admin adds
   rules, so upgrading an existing installation changes nothing by surprise.
3. SMTP credentials live in environment variables, not the database; the settings page shows whether SMTP is
   configured and can send a test message.
4. The role/permission matrix stays defined in code (the seed re-applies it), so the roles screen is read-only.
5. Anonymising a user also redacts that user's name and email inside audit entries about them; the audit entries
   themselves stay.
