# Changelog

All notable changes to ProcuraFlow are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [semantic versioning](https://semver.org/).

## [1.0.0] - release date to be set when the release check passes

Version 1.0.0 turns the earlier procurement, inventory and delivery tool into a complete, self-hosted procure-to-pay
application for small and mid-size companies. It was built in the phases of `PLAN.md`, one commit per step. Items
marked "pending at time of writing" were not finished when this entry was written (see `HANDOFF.md`); confirm them
against the repository before tagging the release.

### Added

- **Company settings (phase 1).** One settings record per installation: company and legal name, address, tax/VAT id,
  logo, brand colour, base currency, fiscal-year start month, date format, time zone, PO number prefix, invoice
  tolerance, default payment terms. New `settings:manage` permission. Public branding endpoint for the sign-in page.
  A storage interface (`app/storage/`) with a local-disk backend, first used for the logo.
- **Currencies and tax (phase 2).** ISO 4217 currencies with hand-maintained exchange rates, editable tax rates
  (VAT or sales tax, inclusive or exclusive, reverse charge), per-line tax snapshots on purchase orders, stored
  subtotal, tax and grand totals, and base-currency totals fixed at approval. Suppliers gain default currency,
  country, VAT number and payment terms. New `finance` role and `finance:manage` permission.
- **Metrics integrity (phase 2 onward).** One service (`metrics_service.py`) owns every business number; definitions
  are documented in `docs/metrics.md` and a consistency test reads each metric through every screen's API.
- **Purchase requests and approvals (phase 3).** Requests with lines, notes and attachments, conversion into draft
  purchase orders, approval rules by document type and amount band with ordered steps copied onto the document,
  delegation for a date range, per-user approval limits, separation of duties, "My approvals" queue. New roles
  `employee` and `department_manager`. Generic attachments with access derived from the parent record.
- **Budgets (phase 3).** Budgets per cost centre and fiscal year with spent, committed and remaining; optional blocking
  of over-budget approvals and a configurable warning level; transfers between cost centres with approval and history.
- **Catalog and amendments (phase 3).** Catalog items with contract price, supplier and lead time; amendments to
  ordered purchase orders with versions, a readable diff, and re-approval when the total rises.
- **Supplier invoices, receipts and payments (phase 4).** Invoices against PO lines with duplicate detection, two-way
  and three-way matching using the settings tolerance, exception handling through the approval rules, goods receipts
  with accepted and rejected quantities, returns to supplier, manual and partial payments, and payment runs that a
  second person must release.
- **Email and documents (phase 5).** Branded PO PDF, an email outbox written inside the business transaction and
  delivered over SMTP (logged instead when SMTP is not configured), editable sandboxed email templates, password reset
  and invitations with hashed single-use tokens, a profile page, a notification centre, and a daily job
  (`python -m app.cli.daily_jobs`) for expiring supplier documents and overdue approvals.
- **Storage, exports and GDPR (phase 6).** Optional S3-compatible storage; upload validation by content signature and
  size; QuickBooks Online and Xero bill CSVs plus PO, invoice and supplier CSVs through one writer that neutralises
  spreadsheet formulas; GDPR export and anonymisation that keep financial records intact; supplier documents with
  computed expiry status; second-approver rule for supplier bank-detail changes; SEPA (pain.001) and NACHA/ACH payment
  files from a released payment run; a lite supplier portal with isolated, scoped access.
- **Design system and redesign (phase 7).** Design tokens with light and dark themes, self-hosted fonts, `Intl`-based
  money and date formatting, a component library with a development-only `/design-system` page, a scope-aware search
  endpoint for the command palette, and every screen redesigned with a grouped sidebar, document pages (request, PO,
  invoice, payment run) and an invoice page. Step 7E, the visual QA loop at three viewport sizes with accessibility
  checks, was pending at time of writing.
- **Landing page and demo mode (phase 8).** In progress at time of writing. `DEMO_MODE`, `ALLOW_DEMO_IN_PRODUCTION`
  and `DEMO_PASSWORD` settings exist in `backend/app/core/config.py`; the demo reset command
  (`python -m app.cli.demo_reset`), the 12-month demo seed and the landing-page Lighthouse targets were not yet
  confirmed.
- **Documentation and deployment (phase 9).** `README.md`, `HowToSetup.md`, `AGENTS.md`, this changelog, a complete
  `.env.example`, `docs/metrics.md`, `docs/sizing.md`, a Docker Compose stack with Caddy and automatic HTTPS
  (`deploy/`), and database backup and restore scripts for Linux/macOS (`.sh`) and Windows (`.ps1`).

### Security

- Production and staging refuse to start with a placeholder, marker-containing, short (under 32 characters) or
  repetitive `JWT_SECRET_KEY`, with a missing, default or short (under 8 characters) database password, and with
  `DEMO_MODE=true` unless `ALLOW_DEMO_IN_PRODUCTION=true`; outside development and test the seed refuses a default or
  short (under 12 characters) admin password.
- Behaviour kept from the earlier releases: short-lived access tokens, rotated refresh tokens in an `HttpOnly`
  cookie, reuse detection, a 30-day absolute session cap, a Postgres-backed sign-in throttle, trusted-proxy hop
  counting for client addresses, role and permission checks on every endpoint, an audit log on every write, and
  record-level scope checks that answer 404 so identifiers cannot be probed.

### Changed

- Frontend dependency versions are pinned exactly; build artefacts are no longer tracked.
- Dashboard and reports read stored base-currency amounts and use the company time zone for "this month".
- Migrations only add or widen columns and tables; each has a working downgrade covered by the round-trip test.

### Known limits and decisions to review

Listed in `PLAN.md` ("Decisions to review") and `HANDOFF.md`. Notably: a rejected purchase order ends as `cancelled`
with the reason kept; approval rules exist only in demo data until an admin adds them; SMTP credentials live in
environment variables; the role matrix is defined in code; account numbers are stored unencrypted; payment files cover
EUR (SEPA) and USD (NACHA) only; supplier emails carry PO details but not the PDF.

### Baseline

The 1.0.0 work started from the application as of commit `06d6cfe` (suppliers, products, purchase orders, inventory
ledger, deliveries, dashboard, reports, RBAC, audit log). See `docs/WORKLOG.md` and `docs/changes/` for its history.
