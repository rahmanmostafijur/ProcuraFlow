# Handover runbook: delivering ProcuraFlow to a company

For the person delivering ProcuraFlow and for the administrator who will run it afterwards. It is a checklist, not a
replacement for [HowToSetup.md](../HowToSetup.md), which has the full commands, or [RELEASE_CHECK.md](../RELEASE_CHECK.md),
which says what was and was not tested.

**Read this first.** A full run of the Docker Compose stack, Caddy certificate issuance, the backup and restore scripts
and email delivery have never been run on a real server. Part 2 is therefore a trial install, and you should not skip it.

## Part 1. Agree these before you start

| Question | Why it matters |
|---|---|
| Who hosts it (their server, a VPS in their name, or yours)? | Whoever hosts it holds the data and is responsible for backups and uptime. Put the answer in the contract. |
| What domain name will they use, and who controls its DNS? | Caddy needs a DNS record pointing at the server before it can issue the HTTPS certificate. |
| What mail account will send email (SMTP host, port, user, password, from-address)? | Invitations and password resets are emails. Without SMTP they are only written to a log. |
| Which currency, fiscal-year start month, time zone and tax rates? | The base currency can only change before the first order has a locked exchange rate. |
| Who are the users, and what role does each get? | See the role table in Part 5. |
| What approval limits do they want (amount bands, who approves, who covers for whom)? | A fresh install has single-step approval until an admin adds rules. |
| Who is their administrator, and who do they call (you) for what? | Decide support scope, response time and who pays for updates before go-live. |
| Licence terms | The README describes a one-time licence; make sure the agreement you give them says the same. |

## Part 2. Trial install on a spare server (do this before delivery day)

Use a throwaway server, with your own domain or `SITE_ADDRESS=localhost`. Time every step; you will need the numbers.

1. Install Docker Engine and the Compose plugin on a Linux server. Open ports 80, 443/tcp and 443/udp.
2. `git clone <repository> /opt/procuraflow && cd /opt/procuraflow`, then check out the release.
3. `cp .env.example .env`, `chmod 600 .env`, then set at least `SITE_ADDRESS`, `ACME_EMAIL`, `POSTGRES_PASSWORD`,
   `JWT_SECRET_KEY`, `DEFAULT_ADMIN_EMAIL`, `DEFAULT_ADMIN_PASSWORD` (12 or more characters), `SMTP_*` and `EMAIL_FROM`.
   Leave `SEED_DEMO_DATA` and `DEMO_MODE` unset.
4. `docker compose --env-file .env -f deploy/docker-compose.yml config` (fails if something required is missing).
5. `docker compose --env-file .env -f deploy/docker-compose.yml up -d --build`, then `... ps` and `... logs -f backend caddy`.
6. Run the post-deployment checks in HowToSetup.md section 6.3 (security headers, `/api/ready`, cookie flags, client
   address in the failed-sign-in log line, throttle, logo survives a restart).
7. Send a test email from the Settings page. Invite one user and confirm the link arrives and works.
8. Run `deploy/backup.sh`, copy the files to another machine, then run `deploy/restore.sh` into this server and confirm
   the data is back. Write down how long the restore took.
9. Walk through the acceptance script in Part 4.
10. Note every problem and fix. Then delete this server, or keep it as your staging copy for updates.

## Part 3. Delivery day

Before the visit: the server is installed (as in Part 2 but with the company's real values), the domain resolves, and the
first administrator can sign in.

1. **Change the admin password** at first sign-in (profile page). Whether sign-in forces this has not been verified.
2. **Settings:** company name, legal name, address, tax id, logo, brand colour, base currency, fiscal-year start month,
   time zone, date format, PO number prefix, invoice tolerance, default payment terms, payer bank details for payment
   files.
3. **Currencies and tax:** enable the currencies they trade in, enter exchange rates (maintained by hand), add tax rates
   (VAT or sales tax, inclusive or exclusive, reverse charge).
4. **Cost centres and budgets:** add budgets per cost centre for the current fiscal year. Choose whether going over a
   budget blocks approval, and the warning percentage.
5. **Approval settings:** add rules by document type and amount band, ordered steps, and per-user limits. Set up
   delegation for anyone who will be away.
6. **Users:** invite each person and assign a role. Invite at least two finance users: the person who creates a
   payment run cannot release it.
7. **Master data:** suppliers (with country, currency, payment terms, VAT number and bank details), products with
   opening stock and minimum stock, and catalog items with contract prices if they use them.
8. **Email templates:** adjust the wording if they want it; the defaults work.
9. **Schedule the jobs** (crontab on the server, adjust the path):

```
10 6 * * *   cd /opt/procuraflow && docker compose --env-file .env -f deploy/docker-compose.yml exec -T backend python -m app.cli.daily_jobs
*/10 * * * * cd /opt/procuraflow && docker compose --env-file .env -f deploy/docker-compose.yml exec -T backend python -m app.cli.send_emails
15 2 * * *   /opt/procuraflow/deploy/backup.sh >> /var/log/procuraflow-backup.log 2>&1
```

10. **Off-server backups:** copy `deploy/backups` somewhere that is not the same disk, on a schedule. Keep `.env` safe
    separately; restoring without the same `JWT_SECRET_KEY` signs everyone out.
11. Hand over credentials (Part 7) and run the acceptance script with their people.

## Part 4. Acceptance script (one purchase, request to payment)

Do it with real people in real roles. If something fails, stop and note it. The steps follow the application's
screens; adjust names if the company renamed anything.

| Step | Who | Where | Expected |
|---|---|---|---|
| 1. Raise a request with a line and a note | Employee | Requests, New | Request is submitted |
| 2. Approve it | Department manager | Approvals | Request approved; the employee cannot approve their own |
| 3. Convert it to a purchase order for a supplier | Purchasing officer | Request page, Convert | A draft purchase order appears |
| 4. Submit the order and approve it | Purchasing officer submits; procurement manager approves | Purchase Orders | Approved; the budget shows it as committed |
| 5. Mark it ordered, download the PDF, email the supplier | Purchasing officer | Order page | PDF has the company name and logo; email arrives (or is queued) |
| 6. Receive part of the delivery | Warehouse manager | Deliveries | Order is partially received; stock rises |
| 7. Receive the rest | Warehouse manager | Deliveries | Order is received |
| 8. Enter the supplier invoice against the order | Finance | Invoices, New | Three-way match result shown per line |
| 9. Approve the invoice | Finance | Invoice page | Status approved; payables outstanding on the dashboard rises |
| 10. Create a payment run | Finance | Payment runs, New | Run is draft |
| 11. Release it | A second finance user | Payment run | Released; the invoice is paid; the payment file can be generated (SEPA for EUR, NACHA for USD) |
| 12. Check the numbers | Admin | Dashboard, Budgets, Reports | The same totals on every screen |

Also check: a supplier portal login sees only that supplier's orders; a viewer cannot change anything; the Audit Log
shows each step with who and when.

## Part 5. Roles in plain words

Taken from the permission matrix in `backend/app/core/permissions.py`.

| Role | Can | Cannot |
|---|---|---|
| Admin | Everything, including users, settings, approval rules and personal-data tools | Approve or release their own documents |
| Procurement manager | Suppliers and bank details, products, catalog; create, move and approve purchase orders; approve requests; enter invoices | Approve invoices or pay |
| Purchasing officer | Create and move purchase orders; raise requests; enter invoices | Approve purchase orders or invoices, pay |
| Warehouse manager | Record deliveries, returns and stock; raise requests | See or enter invoices |
| Finance | Enter and approve invoices; payments, payment runs and payment files; budgets; approval rules; exports; currencies and tax | Release a payment run they created themselves |
| Department manager | Approve requests; ask for budget transfers | Create purchase orders |
| Employee | Raise purchase requests and follow their own | See other people's requests |
| Viewer | Sign in and see what needs no special permission | Change anything |
| Supplier (portal) | See their own orders, invoices and documents; upload documents and draft invoices; change their password | Reach anything internal |

Nobody can approve their own document, and a second person must release a payment run. A record outside someone's scope
answers "not found", so identifiers cannot be probed. Finance cannot see supplier documents (they need the supplier-write
permission); that is one of the decisions in RELEASE_CHECK.md.

## Part 6. Running it afterwards

**Routine**

| When | What |
|---|---|
| Every day | Backup runs; glance at the log. Approvals waiting appear in the sidebar badge. |
| Every week | Check that an off-server copy exists and is recent. `docker compose ... ps` shows all services healthy. |
| Every month | Check disk space and the size of the backup folder. Review users: deactivate leavers rather than deleting them. Enter new exchange rates if they maintain them by hand. |
| Every quarter | Practise a restore into a scratch environment. Run `pip-audit -r backend/requirements.txt` and `npm audit --omit=dev` in `frontend/`. Read the changelog for new versions. |
| Every year | Create next fiscal year's budgets. Review approval limits. Rotate secrets if staff who knew them left. |

**Update**: follow HowToSetup.md section 10. Back up first, check out the new release, compare `.env.example` with `.env`,
run `up -d --build`, then check `ps`, the logs, `/api/ready` and a few screens. Rolling back means restoring the backup.

**Monitoring**: point a free uptime monitor at `https://<domain>/api/ready` (it proves the proxy and the database).

**Leavers and lost passwords**: an admin deactivates the user, or the user requests a reset from the sign-in page.

**Common problems** are in HowToSetup.md section 12 (certificate errors, `429` on sign-in, everyone signed out after a
redeploy, emails not arriving, the backend exiting at start with a weak secret).

## Part 7. What to hand over

- [ ] The repository at the release tag, and `HowToSetup.md`
- [ ] Server address, SSH access, and who holds the domain registrar and DNS logins
- [ ] The filled-in `.env`, stored in their password manager, not sent by email
- [ ] Admin account and the instruction to change its password
- [ ] The backup location, schedule, retention, and the exact restore command, with the measured restore time
- [ ] The crontab and where the logs are
- [ ] A one-page user guide for each role (Part 5 plus the acceptance script)
- [ ] The support agreement: scope, hours, response time, cost of updates, who pays for hosting
- [ ] The licence terms
- [ ] `RELEASE_CHECK.md`, so they know what was verified and the known limits

## Part 8. Tell them honestly

- It is a procure-to-pay tool, not an accounting system or ERP. It exports bills for QuickBooks Online and Xero as CSV; it
  does not keep the general ledger.
- Exchange rates are entered by hand. Payment files cover EUR (SEPA) and USD (NACHA) only.
- Purchase order lines show a product id rather than a name for now.
- Supplier emails carry the order details but not the PDF; the PDF can be downloaded and sent separately.
- Bank account numbers are stored unencrypted in the database, so protect the server and its backups.
- It is built for one company per installation.
- The other known limits and the decisions that are theirs to make are in RELEASE_CHECK.md.

## Part 9. Sign-off

| | Name | Date | Signature |
|---|---|---|---|
| Delivered by | | | |
| Accepted by (company) | | | |

Acceptance script (Part 4) passed on: ______  Restore tested on: ______  First off-server backup confirmed on: ______
