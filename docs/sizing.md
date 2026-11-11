# Sizing and cost

This page helps you pick a server and budget for ProcuraFlow. **Nothing here is a measured benchmark.** The project has
not been load-tested, and no customer figures exist. The tiers are planning starting points derived from what the stack
consists of; the "How to verify" section shows how to replace them with numbers from your own installation within the
first week. Prices change and differ by provider and region, so every price below is a range to re-check on the
provider's own pricing page on the day you buy.

## What actually runs

| Part | Process | Notes from the code |
|---|---|---|
| Caddy | one small static-file and proxy process | serves the built frontend, terminates TLS |
| API | one `uvicorn` process (`backend/start.sh`), async, one worker | no in-process state other than caches; login throttling lives in Postgres, so more instances are possible later |
| PostgreSQL 16 | one server | holds all business data, the audit log and the login throttle |
| Files | local volume (`STORAGE_BACKEND=local`) or any S3-compatible bucket (`STORAGE_BACKEND=s3`) | logo, attachments, supplier documents |
| Cron jobs (optional) | `python -m app.cli.daily_jobs`, `python -m app.cli.send_emails` | short-lived |

The API is a single worker process. For a procurement tool used by office staff (a handful of requests per user per
minute at peak) this is the normal case; if you find it is not, add instances behind Caddy and follow "Migrations and
scaling" in HowToSetup.md, section 11 (`RUN_MIGRATIONS_ON_START=false` plus one migration step).

## Starting-point tiers (estimates, to verify)

| Users (named accounts) | Starting server | Why this is a sensible start |
|---|---|---|
| Up to 10 | 1 vCPU, 2 GB RAM, 20-40 GB SSD | Enough headroom for the OS, Postgres, the API and Caddy to coexist; disk mostly for the database, uploads and a few days of backups |
| Up to 50 | 2 vCPU, 4 GB RAM, 40-80 GB SSD | More concurrent sessions and larger lists; gives Postgres room for its cache |
| Up to 200 | 4 vCPU, 8 GB RAM, 80-160 GB SSD (or a managed Postgres) | Higher concurrency, larger audit log and attachment volume; consider moving the database to a managed service and files to a bucket |

"Users" means accounts that sign in, not concurrent users. Suppliers with portal accounts count too. These tiers
assume ordinary office use; large imports, many simultaneous report exports or very large attachments need more.
Whether 1 GB RAM is enough for a very small team was not tested, so it is not offered as a tier.

## Monthly cost ranges (verify before buying)

The figures are typical public list prices for small virtual servers and managed services at the time of writing, in
US dollars before tax. Treat them as orders of magnitude, not quotes.

### Route A: one VPS with Docker Compose and Caddy (this repository's `deploy/`)

| Item | 10 users | 50 users | 200 users |
|---|---|---|---|
| VPS | about 5-10 | about 10-25 | about 25-60 |
| Off-server backup storage (object storage or a second small disk) | about 1-5 | about 2-10 | about 5-20 |
| Transactional email (SMTP service; many have a free tier at low volume) | 0-10 | 0-15 | 10-30 |
| Domain name (yearly cost divided by 12) | about 1-2 | about 1-2 | about 1-2 |
| TLS certificate | 0 (Let's Encrypt through Caddy) | 0 | 0 |
| **Approximate total** | **about 7-27** | **about 13-52** | **about 41-112** |

### Route B: Render + Neon + Vercel (the existing `render.yaml` and `frontend/vercel.json`)

| Item | Small | Larger |
|---|---|---|
| Render web service | free tier sleeps after 15 minutes idle and takes about a minute to wake (see HowToSetup.md); a paid always-on instance is needed for a real team | paid instance sized like the API row above |
| Neon Postgres | free tier suits a trial; a real installation needs a paid plan with enough storage and no auto-suspend surprises | paid plan |
| Vercel | hobby tier is for non-commercial use; check the terms before running a company on it | paid plan |
| Email, domain | as in route A | as in route A |

Provider plan names, limits and prices change often; this document deliberately gives no figures for route B beyond the
shape of the decision. Total the three current paid plans from their pricing pages. Route B has more moving parts and
three bills; route A has one bill and one server to keep patched.

ProcuraFlow itself is described in `PLAN.md` as a one-time licence with no monthly fee. The ranges above are
infrastructure only. The price and terms of the licence are not in this repository; there is no `LICENSE` file yet.

## Storage growth

Growth comes from four places. The sizes per record are **not measured here**; use the measuring commands below after a
few weeks of real use and extrapolate.

| Source | Grows with | How to measure |
|---|---|---|
| Business tables (orders, lines, invoices, payments, requests, approvals) | documents per month | `SELECT relname, pg_size_pretty(pg_total_relation_size(relid)) FROM pg_catalog.pg_statio_user_tables ORDER BY pg_total_relation_size(relid) DESC LIMIT 15;` |
| Audit log | every write by every user (the log is append-only) | size of the `audit_logs` table from the query above; expect it to be among the largest tables |
| Login throttle and refresh tokens | sign-ins; old rows are purged as new ones arrive | negligible after the first look; confirm with the same query |
| Uploaded files | attachments, supplier documents, the logo | `docker compose exec backend du -sh /app/var/uploads` (or the bucket size) |
| Email outbox | emails sent | size of the `email_outbox` table |

Method for a forecast: record the database size and uploads size on day 1 and again after 30 days of normal use,
subtract, multiply by 12, and add the size of the backups you keep. Backups are `pg_dump` custom-format files
(compressed); keep `BACKUP_RETENTION_DAYS` copies plus one off-server copy, so budget at least
`(database dump size + uploads archive size) x (retention days + 1)` of backup space.

## How to verify (first week)

1. `docker stats --no-stream` during working hours: memory of `postgres`, `backend` and `caddy`. If the host is
   swapping or the three together use more than about 70 percent of RAM, move up a tier.
2. Watch API latency in Caddy's access log or by timing the dashboard in the browser at the busiest hour.
3. Check disk: `df -h` and the queries above, then repeat monthly.
4. Run a backup and a restore into a scratch environment once; record how long each takes. That is your real recovery time.
5. If you serve more users than the tier assumes, run a load test of your own against a staging copy before go-live;
   none has been done for this project.
