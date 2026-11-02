# Metrics

Every number ProcuraFlow shows comes from one place, `backend/app/services/metrics_service.py`, with one definition
per metric. A dashboard card, a report, a badge and an export that show the same figure call the same function, so
they cannot disagree. Tests in `backend/tests/test_metrics_consistency.py` read each metric through every screen's
API and assert the results are identical.

## Rules that apply to every metric

- **Currency.** Amounts are in the company's base currency (Settings > Regional). A purchase order is converted once,
  when it is approved, at the exchange rate in force that day. The converted amounts are stored on the order, so a
  report run next year gives the same figure as one run today, whatever rates are entered later.
- **Time zone.** Calendar periods ("this month", "today") use the company time zone from Settings, not the server's or
  the browser's. An order created at 20:00 UTC on 31 March belongs to April for a company in Tokyo.
- **Exactness.** Money is `Decimal` in the database (`Numeric`) and a decimal string in the API. Each line is rounded
  half-up to the currency's minor units once, and document totals are sums of the rounded lines.
- **Status sets.** The sets below are defined once in code (`COMMITTED_PO_STATUSES`, `PENDING_PO_STATUSES`,
  `COMPLETED_PO_STATUSES`) and imported by every query.

## Status sets

| Set | Purchase order statuses |
|---|---|
| Committed | approved, ordered, partially received, received |
| Pending | draft, submitted, approved, ordered, partially received |
| Completed | received |

Cancelled orders are in none of these sets, and a draft or submitted order is never "committed".

## Metrics

| Metric | Formula | Period | Time zone | Statuses | Shown on |
|---|---|---|---|---|---|
| Total purchase orders | count of purchase orders | all time | n/a | all | Dashboard |
| Pending orders | count of purchase orders | all time | n/a | Pending | Dashboard |
| Completed orders | count of purchase orders | all time | n/a | Completed | Dashboard |
| Active suppliers | count of suppliers with `is_active` | all time | n/a | n/a | Dashboard |
| Inventory value | sum of product cost x current stock, over all products | now | n/a | n/a | Dashboard |
| Low-stock products | count of active products with stock at or below the minimum | now | n/a | n/a | Dashboard |
| Upcoming deliveries | count of deliveries still pending with an expected date of today or later | today | company | n/a | Dashboard |
| Committed spend by month | sum of each order's stored base grand total (tax included), grouped by the month the order was created | last N months | company | Committed | Dashboard chart |
| Orders by month | count of orders in the same groups | last N months | company | Committed | Dashboard chart |
| Committed spend by supplier | sum of the stored base grand total per supplier; suppliers with none show 0 | all time | n/a | Committed | Reports |
| Orders by supplier | count of committed orders per supplier | all time | n/a | Committed | Reports |

Product costs are kept in the base currency, so inventory value needs no conversion.

### Budgets

One row per cost centre and fiscal year, in the base currency. A fiscal year is named after the calendar year it
starts in, from the fiscal year start month in Settings (with an April start, 31 March 2026 is in fiscal year 2025).

| Metric | Formula | Period | Time zone | Statuses |
|---|---|---|---|---|
| Budget | the amount set for the cost centre and fiscal year | fiscal year | n/a | n/a |
| Spent | sum of the stored base grand total of orders charged to the cost centre | fiscal year of the order's approval date (creation date if none) | company | received |
| Committed | the same sum | same | company | approved, ordered, partially received |
| Remaining | budget - spent - committed (negative when overspent) | same | company | n/a |
| Utilisation | (spent + committed) / budget as a percentage, one decimal; empty when the budget is 0 | same | company | n/a |
| Health | `over` when spent + committed exceeds the budget; `warning` from the warning level in Settings; otherwise `ok` | same | company | n/a |

Drafts, submitted and cancelled orders are never counted. The blocking rule (Settings) refuses any approval whose
amount is more than Remaining; an amendment counts only the increase it adds. A cost centre with no budget for the
current fiscal year is not limited.

### Approvals

| Metric | Formula | Shown on |
|---|---|---|
| Waiting for me | documents whose current approval step this user may decide now, directly or as a delegate; the same function the decision endpoints use | My approvals page, sidebar badge |

The badge is the length of the list it links to by construction: both call `approval_queue_service.queue_for`.

### Supplier invoices and payables

Supplier invoices are converted once, when they are approved, at the exchange rate in force that day, exactly like
purchase orders. The rate and the converted totals are stored on the invoice, so payables never move when rates change
later. Payments are in the invoice currency and are converted at the invoice's locked rate.

| Metric | Formula | Period | Time zone | Statuses | Shown on |
|---|---|---|---|---|---|
| Payables outstanding | sum over invoices of (grand total - paid total) x the invoice's locked rate, each invoice rounded half-up to the base currency's minor units | now | n/a | approved | Dashboard, invoice list totals |
| Overdue payables | the same sum, restricted to invoices whose due date is before today | today | company | approved | Dashboard, invoice list totals |
| Invoices by status | count of invoices per status, every status listed (zero when none) | all time | n/a | all | Invoice list totals |
| Invoices needing attention | matched + exception invoices | all time | n/a | matched, exception | Dashboard, invoice list totals |

Invoices on hold, void, paid or not yet approved are not payables: on hold means payment is paused and the invoice is
no longer counted until it is released. An invoice that is due today is not overdue. The invoice list takes the same
filters (status, supplier, order, due before, number search) as these functions, so its totals for a set of filters
equal the dashboard figures for the same filters (with no filters, the dashboard figures).

Invoice matching compares quantities with the accepted quantity of an order line (units received minus units rejected),
so a rejected delivery never counts as received for matching or for the order's status.

### Figures computed outside `metrics_service.py`

Five figures are not in `metrics_service.py`. They are single-purpose and each has exactly one implementation, but they
do not yet carry a cross-screen consistency test, so verify before relying on a second place that shows them.

| Figure | Formula | Where it lives | Shown on |
|---|---|---|---|
| On-time delivery rate | deliveries with an actual date that are `on_time`, divided by all deliveries with an actual date, times 100, rounded to one decimal; 0 when there are none | `delivery_service.get_on_time_delivery_rate` | Reports |
| Delayed deliveries | deliveries with status `delayed`; variance = actual date - expected date in days (empty if either date is missing) | `routers/reports.py` | Reports |
| Delivery status | set when goods are received: all ordered units received gives `on_time` if the actual date is on or before the expected date (or there is no expected date), else `delayed`; fewer gives `partial` | `goods_receipt_service._update_delivery` | Deliveries page, Reports |
| Supplier document status | no expiry date: valid; expiry before today: expired; expiry within 30 days from today: expiring soon; otherwise valid. Computed on every read, never stored | `supplier_document_service` | Dashboard card "documents expiring soon", supplier documents |
| Inventory status CSV | per product: stock, minimum, cost, stock = current stock x cost, low-stock flag (stock at or below the minimum) | `routers/reports.py` | Reports (CSV download) |

The "actual date" of a delivery is the day (UTC) goods were last received.

## Where each figure comes from, and where it is shown

| Metric | Source tables | Screens and endpoints |
|---|---|---|
| Total, pending, completed orders | `purchase_orders` | Dashboard (`GET /dashboard/summary`) |
| Active suppliers | `suppliers` | Dashboard |
| Inventory value, low-stock products | `products` | Dashboard, Reports CSV |
| Upcoming deliveries | `deliveries` | Dashboard |
| Committed spend by month, orders by month | `purchase_orders` (stored `base_grand_total`, `created_at`) | Dashboard chart (`GET /dashboard/monthly-trends`) |
| Committed spend and orders by supplier | `purchase_orders`, `suppliers` | Reports (`GET /reports/supplier-performance`) |
| Budget, spent, committed, remaining, utilisation, health | `budgets`, `cost_centres`, `purchase_orders`, `company_settings` | Budgets page and Dashboard "budget health" (`GET /budgets`), the approval check in `budget_service.enforce_budget` |
| Waiting for me | `approval_steps`, `approval_delegations`, `approval_limits` and the documents they point at | My approvals page, sidebar badge, Dashboard "waiting for you" (`GET /approvals/queue`) |
| Payables outstanding, overdue payables | `supplier_invoices`, `currencies` (minor units), `company_settings` | Dashboard, invoice list totals (`GET /supplier-invoices`) |
| Invoices by status, needing attention | `supplier_invoices` | Dashboard, invoice list totals |

The trend window: "last N months" starts at the first day of the current month in the company time zone minus
N x 31 days, so the current, partial month is always included. N is 6 by default and 1 to 24 on request.

## How reconciliation is guaranteed

1. **One definition, one function.** A screen, report, badge or export calls the function in `metrics_service.py`;
   routers do not run their own aggregate queries for these figures. The status sets (`COMMITTED_PO_STATUSES`,
   `PENDING_PO_STATUSES`, `COMPLETED_PO_STATUSES`, `ATTENTION_INVOICE_STATUSES`) are defined once and imported.
2. **Stored amounts, not recomputed ones.** Orders and invoices store their base-currency totals at approval, with the
   exchange rate that was in force. Later rate changes never alter past reports.
3. **Same filters, same functions.** The invoice list and the dashboard call the same payables and count functions
   with the same filter object, so list totals equal the dashboard figures for the same filters.
4. **Same list, same badge.** The approvals badge is `len(queue_for(user))`, the list itself.
5. **Tests.** `backend/tests/test_metrics_consistency.py` reads each metric through every screen's API and asserts
   equality: spend by supplier and by month sum to the same total; foreign-currency orders count at their locked base
   amount; the company time zone decides the month; the approvals badge equals the queue length; budget figures agree
   with the spend report; dashboard counts match the order lists; payables and invoice counts agree between the
   dashboard, the invoice list and the service. `test_spend_metrics.py`, `test_invoice_metrics.py` and
   `test_budgets.py` cover the individual definitions.

What the guarantee does **not** cover: the figures in the table "Figures computed outside `metrics_service.py`", and
any figure you export and edit yourself. After a data import or a manual database change, re-run the backend tests
`test_metrics_consistency.py` and spot-check the dashboard against an order list.

## Adding a metric

1. Write one function in `metrics_service.py` and document it in the table above.
2. Make every router, export and badge that shows it call that function.
3. Add a test to `test_metrics_consistency.py` that reads it through each screen's API and compares the results.
