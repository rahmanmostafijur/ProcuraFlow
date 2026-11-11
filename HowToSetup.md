# How to set up ProcuraFlow

This guide covers running ProcuraFlow on your own machine for development and on a server for production.
It states only what the repository does. Where something could not be verified here, it says what to check.

Contents: [1. Prerequisites](#1-prerequisites) - [2. Configuration](#2-configuration) -
[3. Local development](#3-local-development) - [4. Database and migrations](#4-database-and-migrations) -
[5. Running the tests](#5-running-the-tests) - [6. Production with Docker Compose and Caddy](#6-production-with-docker-compose-and-caddy) -
[7. First administrator](#7-first-administrator) - [8. Scheduled jobs](#8-scheduled-jobs) -
[9. Backups and restore](#9-backups-and-restore) - [10. Upgrading](#10-upgrading) -
[11. Alternative: Render, Neon and Vercel](#11-alternative-render-neon-and-vercel) - [12. Troubleshooting](#12-troubleshooting)

## 1. Prerequisites

| Tool | Needed for | Version |
|---|---|---|
| Python | backend development and tests | 3.12 |
| Node.js and npm | frontend development and build | 20 or newer (CI uses 22) |
| PostgreSQL | database | 16 (Docker is the easiest way) |
| Docker with Compose v2 | production deployment, or a throwaway local database | any recent version |
| Git | getting the code | any |

Install them per platform:

- **Windows.** Install Python 3.12 from python.org (tick "Add to PATH"), Node.js LTS from nodejs.org, Git for Windows,
  and Docker Desktop (needs WSL 2). Use PowerShell. The Linux-style commands below have a PowerShell form where they differ.
- **macOS.** `brew install python@3.12 node git` and Docker Desktop (or Colima).
- **Linux.** Use your package manager for Python 3.12 (with `venv`), Node.js, Git, and install Docker Engine with the
  Compose plugin from Docker's documentation. On a production server, install nothing else: Docker runs the rest.

## 2. Configuration

All configuration is environment variables, documented in [`.env.example`](.env.example). Copy it and edit:

| Where you run | Copy it to |
|---|---|
| Local backend | `backend/.env` (the backend reads `.env` from the directory it starts in) |
| Docker Compose | `.env` at the repository root |

```bash
cp .env.example backend/.env       # local development
cp .env.example .env               # Docker Compose
```

```powershell
Copy-Item .env.example backend\.env
Copy-Item .env.example .env
```

Settings you must understand before going beyond your own machine:

| Setting | Rule |
|---|---|
| `ENVIRONMENT` | `development`, `test`, `staging` or `production`. The default when unset is `production`. |
| `JWT_SECRET_KEY` | Required. Outside development and test it must not be a known placeholder or contain a marker such as `change-me`, must be at least 32 characters with at least 10 different ones, or the API refuses to start. Generate: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `DEFAULT_ADMIN_EMAIL`, `DEFAULT_ADMIN_PASSWORD` | The first administrator. Outside development and test the seed refuses a default password or one under 12 characters. |
| `DATABASE_URL` | `postgresql+asyncpg://user:password@host:5432/db`. Plain `postgresql://` URLs from a provider are rewritten automatically. Use `127.0.0.1`, not `localhost`, on Windows. |
| `TRUSTED_PROXY_HOPS` | Number of reverse proxies in front of the API: 0 for local, 1 behind Caddy (set by the compose file). |
| `CORS_ORIGINS` | Leave unset when the browser reaches the API through the same-origin `/api` proxy (both supported deployments do). |
| `STORAGE_BACKEND` | `local` (a volume) or `s3` (all five `S3_*` settings then required). |
| `SMTP_HOST` and related | Without `SMTP_HOST`, emails are queued in the outbox and logged, not sent. |
| `SEED_DEMO_DATA` | Sample suppliers and products. Off in staging and production unless you set it. |
| Database password | Outside development and test the password in `DATABASE_URL` (and `MIGRATION_DATABASE_URL`) must exist, be at least 8 characters and not a common default (`procuraflow`, `postgres`, `password`, `admin`, ...), or the API refuses to start. With Compose this is `POSTGRES_PASSWORD`. |
| `DEMO_MODE`, `ALLOW_DEMO_IN_PRODUCTION`, `DEMO_PASSWORD` | Public demo: sign in as a role without a password, destructive admin actions blocked, email only logged. **Never on an installation with real data.** `DEMO_MODE=true` with `ENVIRONMENT=production` is refused unless `ALLOW_DEMO_IN_PRODUCTION=true`. `DEMO_PASSWORD` (12 or more characters) is optional; unset, it is derived from `JWT_SECRET_KEY`. |

Never commit a real `.env` (it is git-ignored) and never paste secrets into issues or screenshots.

## 3. Local development

### 3.1 A local database

Skip this if you already have PostgreSQL 16. With Docker:

```bash
docker run -d --name procuraflow-db \
  -e POSTGRES_USER=procuraflow -e POSTGRES_PASSWORD=procuraflow -e POSTGRES_DB=procuraflow \
  -p 127.0.0.1:5432:5432 postgres:16-alpine
```

(PowerShell: the same command with the backslash line breaks replaced by backticks, or on one line.)

### 3.2 Backend

```bash
cd backend
python -m venv .venv
. .venv/bin/activate                    # macOS/Linux
pip install -r requirements-dev.txt     # runtime plus test and lint tools
cp ../.env.example .env
alembic upgrade head
python -m app.seeds.seed
uvicorn app.main:app --reload
```

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1              # if scripts are blocked: Set-ExecutionPolicy -Scope Process Bypass
pip install -r requirements-dev.txt
Copy-Item ..\.env.example .env
alembic upgrade head
python -m app.seeds.seed
uvicorn app.main:app --reload
```

The API is at <http://localhost:8000>; interactive docs at `/docs` and `/redoc`; `/health` answers 200 without a database
and `/api/ready` answers 200 only when the database is reachable.

### 3.3 Frontend

```bash
cd frontend
npm ci
npm run dev
```

The app is at <http://localhost:5173>. In development it calls `http://localhost:8000/api/v1`; override with
`VITE_API_BASE_URL` in `frontend/.env` if your backend runs elsewhere. The `/design-system` page exists only in the
development server.

### 3.4 Sign in

Use `DEFAULT_ADMIN_EMAIL` and `DEFAULT_ADMIN_PASSWORD` from your `.env`.

## 4. Database and migrations

- The schema is created and changed only by Alembic migrations in `backend/alembic/versions/`. From an empty database,
  `alembic upgrade head` builds everything.
- Create a new migration after changing a model: `alembic revision --autogenerate -m "describe the change"`, then read
  and edit the generated file. Migrations here only add or widen; each needs a working `downgrade()`.
- Roll back one step: `alembic downgrade -1`. Show the current revision: `alembic current`.
- Behind a transaction-pooling PgBouncer (for example Neon's `-pooler` host), set `MIGRATION_DATABASE_URL` to the direct
  connection string. Migrations hold a session-level advisory lock that a transaction pooler cannot keep.
- The seed (`python -m app.seeds.seed`) is idempotent. It creates roles and permissions, re-applies the permission
  matrix from `app/core/permissions.py` (so permission edits made directly in the database are overwritten by design),
  and creates the first admin if missing. Demo data goes only into an empty database and only when enabled.

## 5. Running the tests

Backend tests need their own PostgreSQL database; they create and drop tables, so never point them at real data.

```bash
docker exec procuraflow-db psql -U procuraflow -c "CREATE DATABASE procuraflow_test;"
cd backend
export TEST_DATABASE_URL=postgresql+asyncpg://procuraflow:procuraflow@127.0.0.1:5432/procuraflow_test
python -m pytest -q
ruff check . && ruff format --check . && mypy
```

```powershell
cd backend
$env:TEST_DATABASE_URL = "postgresql+asyncpg://procuraflow:procuraflow@127.0.0.1:5432/procuraflow_test"
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

Run only one pytest process at a time (they share the test database). The full suite takes a long time; run the files
you changed first. Frontend:

```bash
cd frontend
npm test && npm run typecheck && npm run lint && npm run format:check && npm run build
```

## 6. Production with Docker Compose and Caddy

The stack in [`deploy/docker-compose.yml`](deploy/docker-compose.yml) has three services: `postgres` (with a health
check and a named volume), `backend` (the API image from `backend/Dockerfile`, non-root user, its own health check,
an uploads volume) and `caddy` (serves the built frontend, proxies `/api/*` to the backend, obtains and renews HTTPS
certificates automatically). Only Caddy publishes ports (80, 443). All services restart unless stopped.

### 6.1 Server

- A Linux server with Docker Engine and the Compose plugin; see [docs/sizing.md](docs/sizing.md) for sizing.
- A domain name whose DNS `A` (and `AAAA`) record points at the server's public address, **before** you start Caddy.
- Ports 80 and 443 (TCP, and 443/UDP for HTTP/3) open in the firewall and the provider's network rules.
  Port 80 is needed for the certificate challenge and for the redirect to HTTPS.

### 6.2 Step by step

1. **Get the code** on the server: `git clone <your repository URL> /opt/procuraflow && cd /opt/procuraflow`, then
   check out the release tag or branch you intend to run.
2. **Create the environment file**: `cp .env.example .env` and edit `.env`. At minimum set:
   - `SITE_ADDRESS` (for example `procure.example.com`) and `ACME_EMAIL`
   - `POSTGRES_PASSWORD` (letters and digits; `openssl rand -hex 24` works)
   - `JWT_SECRET_KEY` (32 or more characters; `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`)
   - `DEFAULT_ADMIN_EMAIL` and `DEFAULT_ADMIN_PASSWORD` (a unique password of 12 or more characters)
   - SMTP settings if the system should send email (invitations and password resets depend on it), and `EMAIL_FROM`
   - leave `SEED_DEMO_DATA` unset for a real installation

   The compose file sets `ENVIRONMENT=production`, builds `DATABASE_URL` from the Postgres values, sets
   `TRUSTED_PROXY_HOPS=1` and `APP_BASE_URL=https://<SITE_ADDRESS>`; values there win over `.env`.
   Protect the file: `chmod 600 .env`.
3. **Check the configuration**: `docker compose --env-file .env -f deploy/docker-compose.yml config` prints the resolved
   file and fails if a required value is missing.
4. **Build and start**: `docker compose --env-file .env -f deploy/docker-compose.yml up -d --build`. The first build
   downloads images and compiles the frontend; the backend then runs `alembic upgrade head` and the seed before serving.
5. **Watch it come up**: `docker compose --env-file .env -f deploy/docker-compose.yml ps` and `... logs -f backend caddy`.
   The backend reports healthy when `/health` answers; Caddy then obtains the certificate. If the backend exits at
   start, the log says why (typically a weak secret or admin password; see [Troubleshooting](#12-troubleshooting)).
6. **Open `https://<SITE_ADDRESS>`** and sign in as the admin ([7. First administrator](#7-first-administrator)).
7. **Verify the deployment** with the checks in [6.3](#63-post-deployment-checks), then set up
   [backups](#9-backups-and-restore) and [scheduled jobs](#8-scheduled-jobs) before real data goes in.

To save typing, from the repository root: `alias pfc='docker compose --env-file .env -f deploy/docker-compose.yml'`.

### 6.3 Post-deployment checks

- `curl -I https://<SITE_ADDRESS>/` shows the security headers set in the Caddyfile (`Content-Security-Policy`,
  `Strict-Transport-Security`, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`).
- `curl https://<SITE_ADDRESS>/api/ready` returns 200 (proves the proxy and the database).
- After signing in, the browser shows a `refresh_token` cookie that is `HttpOnly`, `Secure`, `SameSite=Lax` with path
  `/api/v1/auth`; a hard reload keeps you signed in.
- **Client address trust.** Fail one sign-in with a wrong password for a throwaway account, then read the backend log:
  `docker compose ... logs backend | grep "failed sign-in"`. The line `failed sign-in client_ip=<address>
  forwarded_entries=<n>` should show your public address with `forwarded_entries=1`. If `client_ip` is `None`, the
  proxy chain is not the one assumed; check how traffic reaches Caddy (a load balancer or CDN in front adds a hop, and
  `TRUSTED_PROXY_HOPS` must then match). If it shows an internal address, do not raise the value; investigate.
- Five wrong passwords on a throwaway account produce `429` with `Retry-After`; restart the backend
  (`docker compose ... restart backend`) and the account is still locked (the throttle is stored in Postgres).
- Upload a company logo in Settings and confirm it survives `docker compose ... restart backend` (the uploads volume).
- The interactive docs `/docs` and `/openapi.json` are **not** reachable from outside, because Caddy forwards only
  `/api/*`. Verify with `curl -I https://<SITE_ADDRESS>/docs` (it serves the single-page app, not the docs).

Not verified in this repository: a full run of the Compose stack and Caddy certificate issuance on a real server.
Treat your first deployment as the verification and keep the checks above.

### 6.4 Trying the stack on your own machine

Set `SITE_ADDRESS=localhost` and start as above. Caddy issues a certificate from its own local authority, so the browser
warns once. Use a `POSTGRES_PASSWORD` and `JWT_SECRET_KEY` of your own even for a trial.

### 6.5 Optional: S3-compatible file storage

Set `STORAGE_BACKEND=s3` and all of `S3_ENDPOINT_URL`, `S3_BUCKET`, `S3_REGION`, `S3_ACCESS_KEY_ID`,
`S3_SECRET_ACCESS_KEY` in `.env`. The API checks them at start and refuses to run half-configured. Files then live in the
bucket, so `backup.sh` backs up only the database part that matters; back the bucket up with your provider's tools.

## 7. First administrator

On start, `backend/start.sh` runs the seed, which creates the roles and permissions and **one administrator** from
`DEFAULT_ADMIN_EMAIL` and `DEFAULT_ADMIN_PASSWORD`. That is the only account a fresh installation has.

1. Sign in with those values.
2. Open the profile page and change the password to one only you know.
3. In Settings, enter company details, base currency, fiscal-year start month, time zone and tax rates **before** the
   first purchase order: the base currency can only change while no order has a locked exchange rate.
4. In Users, invite colleagues and assign roles (admin, procurement manager, purchasing officer, warehouse manager,
   finance, department manager, employee, viewer). Invitations and password resets are emails; without SMTP they are
   queued and logged, so configure `SMTP_*` first or take the link from the log.
5. Optionally set `SEED_ON_START=false` in `.env` once the first admin exists to skip the seed on later starts. The
   seed is idempotent, so leaving it on is also safe.

A fresh installation keeps single-step approval until an administrator adds approval rules (they are seeded only with
demo data). Add rules under approval settings before relying on multi-step approval.

Whether the first sign-in forces a password change is not verified here; change it anyway.

## 8. Scheduled jobs

Two commands are meant for cron. Run them inside the backend container:

```bash
docker compose --env-file .env -f deploy/docker-compose.yml exec -T backend python -m app.cli.daily_jobs
docker compose --env-file .env -f deploy/docker-compose.yml exec -T backend python -m app.cli.send_emails
```

- `daily_jobs`: creates notifications for expiring supplier documents and overdue approvals. Run once a day.
- `send_emails`: retries queued messages (after a mail outage). Run every few minutes if you rely on email.

Example crontab (adjust the path):

```
10 6 * * *   cd /opt/procuraflow && docker compose --env-file .env -f deploy/docker-compose.yml exec -T backend python -m app.cli.daily_jobs
*/10 * * * * cd /opt/procuraflow && docker compose --env-file .env -f deploy/docker-compose.yml exec -T backend python -m app.cli.send_emails
15 2 * * *   /opt/procuraflow/deploy/backup.sh >> /var/log/procuraflow-backup.log 2>&1
```

A demo installation (`DEMO_MODE=true`) restores its data nightly with `python -m app.cli.demo_reset`, for example
`10 3 * * *   cd /opt/procuraflow && docker compose --env-file .env -f deploy/docker-compose.yml exec -T backend python -m app.cli.demo_reset`.
The command deletes every table except roles, permissions and currencies before it builds the demo company, and the only
thing that stops it on a real database is `DEMO_MODE` being off, so never set `DEMO_MODE=true` on an installation that
holds real data. In production the application refuses `DEMO_MODE=true` unless `ALLOW_DEMO_IN_PRODUCTION=true` is also set.

## 9. Backups and restore

What to back up: the PostgreSQL database and, with `STORAGE_BACKEND=local`, the uploads volume. The scripts do both.

**Back up** (Linux and macOS; run from anywhere; the stack must be running):

```bash
deploy/backup.sh                 # writes to deploy/backups
deploy/backup.sh /mnt/backups    # or another directory
```

```powershell
.\deploy\backup.ps1
.\deploy\backup.ps1 -BackupDir D:\backups\procuraflow
```

Each run writes `procuraflow-db-<UTC timestamp>.dump` (`pg_dump` custom format) and
`procuraflow-uploads-<UTC timestamp>.tar.gz`, then deletes backups older than `BACKUP_RETENTION_DAYS` (default 14) from
that directory. Files are written under a temporary name and renamed when complete, so an interrupted run leaves no
file that looks finished. **Copy the files off the server** (object storage, another machine). A backup on the same
disk does not protect against losing the disk. The `.env` file holds your secrets and is not backed up by the script;
store it somewhere safe separately, because restoring data without the same `JWT_SECRET_KEY` signs everyone out.

**Restore** replaces the current content of the database, so it asks you to type the database name first:

```bash
deploy/restore.sh deploy/backups/procuraflow-db-20260101T020000Z.dump
deploy/restore.sh <dump> <uploads-archive>          # also restore uploaded files
deploy/restore.sh <dump> <uploads-archive> --yes    # skip the prompt (automation)
```

```powershell
.\deploy\restore.ps1 -DatabaseDump .\deploy\backups\procuraflow-db-20260101T020000Z.dump
.\deploy\restore.ps1 -DatabaseDump <dump> -UploadsArchive <archive> -Yes
```

The script stops the API, restores with `pg_restore --clean --if-exists`, restores files if you gave an archive, and
starts the API again, which applies any newer migrations. Practise a restore into a scratch environment **before** you
need one, and time it; that time is your real recovery time. These scripts were syntax-checked but not run against a
live Compose stack in this repository, so run one backup and one restore on a test copy first.

## 10. Upgrading

1. Read [CHANGELOG.md](CHANGELOG.md) for the new version.
2. **Back up** (section 9) and keep the backup until you are sure.
3. `git fetch && git checkout <new tag or branch>`.
4. Compare `.env.example` with your `.env` and add any new settings.
5. `docker compose --env-file .env -f deploy/docker-compose.yml up -d --build`. The backend applies migrations on start
   (`RUN_MIGRATIONS_ON_START` defaults to true; migrations are serialised by an advisory lock).
6. Check `docker compose ... ps`, the logs, `/api/ready` and a few screens.
7. To roll back: restore the previous code and the backup from step 2 (migrations have downgrades, but restoring a
   backup is the dependable way).

Do not change the Postgres image to a new **major** version by editing the tag: dump with `pg_dump`, start the new
version on a fresh volume and restore. Pinned image tags in the compose file and Dockerfiles should be checked with
`docker pull` before the first build and bumped deliberately.

## 11. Alternative: Render, Neon and Vercel

The repository also contains `render.yaml` and `frontend/vercel.json` for a hosted route: **Neon** (PostgreSQL),
**Render** (API container) and **Vercel** (static frontend). Vercel proxies `/api/*` to Render, so the browser talks to
one origin and needs no CORS configuration. Costs are discussed in [docs/sizing.md](docs/sizing.md).

1. **Neon.** Create a project. Copy the pooled (`-pooler`) and the direct connection strings.
2. **Render.** New, Blueprint, pointing at this repository. Provide `DATABASE_URL` (pooled), `DEFAULT_ADMIN_EMAIL`,
   `DEFAULT_ADMIN_PASSWORD` (unique, 12 or more characters), and add `MIGRATION_DATABASE_URL` set to the **direct**
   string. `JWT_SECRET_KEY` is generated by Render. `render.yaml` presets `TRUSTED_PROXY_HOPS=2` (client to Vercel to
   Render) and `SEED_DEMO_DATA=true`; delete the latter for a real installation.
3. **Vercel.** Edit the `/api` rewrite `destination` in `frontend/vercel.json` to your Render hostname, commit, import the
   repository with Root Directory `frontend`. No environment variables.
4. **Verify** with the list below.

Render's free tier sleeps after 15 minutes idle and takes about a minute to wake; the sign-in page shows a waking
notice meanwhile. To scale past one instance, run `alembic upgrade head` as a pre-deploy step and set
`RUN_MIGRATIONS_ON_START=false`.

Hop count: `TRUSTED_PROXY_HOPS=2` assumes Vercel sets the client address and Render appends its peer. That assumption is
**unverified until the first deployment**. Fail one sign-in through the Vercel URL and read the Render log line
`failed sign-in client_ip=<address> forwarded_entries=<n>`; expect your public address and `2`. If it is `None` with another
count, set the variable to that count. If it is a Vercel or Render address, do not raise it. Someone who reaches the
Render URL directly can choose their own client address for the per-address check; only restricting direct access closes
that (a paid Render feature). The per-account limit is unaffected.

Post-deployment checks for this route (none has been run against real Render, Neon or Vercel yet):

1. `https://<render-service>/health` and `/api/ready` return 200, and so does `https://<vercel-app>/api/ready`.
2. After 15 or more minutes idle, the sign-in page shows the waking notice and never spins forever.
3. The `refresh_token` cookie is `HttpOnly`, `Secure`, `SameSite=Lax`, path `/api/v1/auth`, on the Vercel domain; the
   login response body contains no refresh token.
4. A hard reload keeps you signed in and the cookie value changes (rotation); two tabs reloading at once both stay signed in.
5. Refresh-token reuse after the grace window returns 401 and an admin sees `refresh_token_reuse` in the audit log.
6. Logout clears the cookie while a second browser stays signed in; an admin changing the user's password signs the
   second browser out too.
7. Five wrong passwords on a throwaway account give `429`; the throttle survives a Render restart.
8. A deep link such as `/suppliers` loads, security headers are present (`curl -I`), and no Content-Security-Policy
   violations appear in the console (Vercel preview deployments inject a toolbar script the policy blocks; production does not).
9. Render's logs show migrations reaching the latest revision.

To build and try the production API image alone:

```bash
docker build -t procuraflow-api backend
docker run --rm -p 8000:8000 -e ENVIRONMENT=production \
  -e DATABASE_URL=postgresql://user:pass@host/db \
  -e JWT_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')" \
  -e DEFAULT_ADMIN_EMAIL=admin@example.com -e DEFAULT_ADMIN_PASSWORD='a-unique-12+char-password' \
  procuraflow-api
```

## 12. Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| `docker compose config` says `Set POSTGRES_PASSWORD in .env` (or another variable) | A required value is empty. Edit `.env`; pass `--env-file .env` as shown. |
| Backend container exits at start with `JWT_SECRET_KEY ... placeholder` or `at least 32 characters` | Weak secret in production. Generate a long random one and `up -d` again. |
| Backend exits with `DATABASE_URL has no password, a default one or a very short one` | Set a strong `POSTGRES_PASSWORD` (8 or more characters, not a common default). If the volume already exists with the old password, change it inside Postgres too (see the `password authentication failed` row). |
| Backend exits with `DEMO_MODE=true is refused when ENVIRONMENT=production` | Remove `DEMO_MODE`, or for a deliberate public demo add `ALLOW_DEMO_IN_PRODUCTION=true`. |
| Backend exits with `DEFAULT_ADMIN_PASSWORD ... known default` or `at least 12 characters` | Set a unique admin password of 12 or more characters. |
| Backend exits with `STORAGE_BACKEND=s3 needs these settings` | Fill every `S3_*` value or use `STORAGE_BACKEND=local`. |
| Browser shows a certificate error or Caddy logs ACME failures | DNS does not point at the server yet, ports 80/443 are blocked, or `SITE_ADDRESS` is wrong. Fix, then `docker compose ... restart caddy`. Let's Encrypt rate-limits repeated failures; use `localhost` to test the stack first. |
| 502 or 504 from `/api/...` | The backend is starting or unhealthy. `docker compose ... ps` and `logs backend`. Large uploads wait up to 120 s. |
| `429` on sign-in | The throttle (5 failures per account, 20 per address, 15 minutes by default). Wait for `Retry-After`. If everyone is blocked together, the client address is wrong: check `TRUSTED_PROXY_HOPS` (section 6.3). |
| Everyone signed out after a restore or redeploy | `JWT_SECRET_KEY` changed. Restore the original `.env` value. |
| Database errors `password authentication failed` | `POSTGRES_PASSWORD` was changed after the volume was first created; the database keeps its original password. Change it inside Postgres (`ALTER USER`) or recreate the volume (destroys data). |
| `localhost` is very slow on Windows | Use `127.0.0.1` in database URLs. |
| `pytest` cannot connect | `TEST_DATABASE_URL` missing or the test database does not exist (section 5). |
| `alembic upgrade head` hangs behind a pooler | Set `MIGRATION_DATABASE_URL` to the direct connection string. |
| Emails never arrive | `SMTP_HOST` is unset (messages are only logged), or the SMTP settings are wrong. Check the `email_outbox` table for the last error and run `python -m app.cli.send_emails`. |
| Port 80 or 443 already in use | Another web server runs on the host. Stop it or change the published ports in the compose file (certificate issuance needs 80 and 443 reachable from the internet). |
| Caddy cannot bind ports as a non-root user | The Caddy image grants the binary the capability to bind low ports; if your runtime drops it, add `cap_add: [NET_BIND_SERVICE]` to the `caddy` service. Not verified on every runtime. |

Logs: `docker compose --env-file .env -f deploy/docker-compose.yml logs --tail 200 <service>`.
