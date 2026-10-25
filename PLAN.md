# ProcuraFlow 1.0 plan

Goal: turn ProcuraFlow into a complete, self-hosted procure-to-pay product for small and mid-size companies in the
US and Europe. Work happens on the `vibe96` branch, one phase at a time, one conventional commit per phase after
backend tests, frontend tests, type-check, lint and build are green. Nothing is pushed or deployed.

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

## Phase 4: supplier invoices, matching and payments

- `supplier_invoices` + lines against PO lines, attachment for the PDF/image, duplicate check on supplier +
  invoice number, due date from payment terms.
- Two-way (price) and three-way (price + received quantity, cumulative across invoices) matching using the
  settings tolerance. Mismatches are stored as reasons and become `exception`, which goes through the approval rules.
- Statuses: draft, matched, exception, approved, on hold, paid, void. Manual payments (bank transfer, card, cheque),
  partial payments allowed, never above the open amount; fully paid invoices become `paid`.
- Permissions `invoice:read`, `invoice:write`, `invoice:approve`, `payment:write`.

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

## Phase 6: attachments, exports and GDPR

- S3-compatible storage backend (optional, selected by environment). Upload validation by content signature and
  size; downloads only for users who can see the parent record.
- Accounting CSVs: bills in QuickBooks Online and in Xero import layouts, plus POs, invoices and suppliers, all
  through one shared writer that applies the existing formula-injection protection.
- GDPR (`gdpr:manage`, admin): JSON export of a user's or supplier contact's personal data; anonymisation that keeps
  financial records intact; both recorded in the audit log.

## Phase 7: design system and redesign

- Tokens as CSS variables (colour, radius, shadow, spacing, type) wired into `tailwind.config.ts`; Plus Jakarta Sans
  self-hosted via `@fontsource`; ink/navy neutrals, emerald/teal brand, amber accent; light and dark themes with a
  toggle, WCAG AA contrast, `prefers-reduced-motion` honoured.
- Component set: buttons, inputs, selects, date picker, data table (sort, filter, paginate, sticky header), badges,
  KPI cards, modal, drawer, tabs, toasts, skeletons, SVG empty-state illustrations, confirm dialog, Ctrl+K search
  (backed by a scope-aware `/search` endpoint).
- Every screen redesigned, responsive to 360px, keyboard accessible. Routes are code-split.

## Phase 8: landing page and demo mode

- Public landing page at `/` (signed-in users go to `/dashboard`).
- `DEMO_MODE=true`: one-click role sign-in on the login page, destructive admin actions blocked, email logged only,
  and `python -m app.cli.demo_reset` restores the demo data (for a nightly cron).
- Realistic seed for a fictional US/EU company across 12 months in USD, EUR and GBP, created through the services
  so totals, approvals, matching and stock all agree.

## Phase 9: documentation and deployment

- README, HowToSetup.md, AGENTS.md, CHANGELOG.md (1.0.0), complete `.env.example`; production refuses weak secrets.
- Docker Compose route with Caddy (automatic HTTPS) and database backup/restore scripts; the existing Render + Neon +
  Vercel route; sizing and monthly cost for both.
- Playwright script that captures 8+ screenshots at 1920x1080 into `docs/screenshots/`.

## Final check

All tests, type-check, lint, build, `pip-audit`, `npm audit --omit=dev`, an attribution scan over every commit on the
branch, then `RELEASE_CHECK.md`. Stop and wait.

## Decisions to review

1. Rejected POs go back to `draft` (new `submitted -> draft` transition). Alternative: reject means cancel.
2. Approval rules are seeded only with demo data. A fresh install keeps single-step approval until an admin adds
   rules, so upgrading an existing installation changes nothing by surprise.
3. SMTP credentials live in environment variables, not the database; the settings page shows whether SMTP is
   configured and can send a test message.
4. The role/permission matrix stays defined in code (the seed re-applies it), so the roles screen is read-only.
5. Anonymising a user also redacts that user's name and email inside audit entries about them; the audit entries
   themselves stay.
