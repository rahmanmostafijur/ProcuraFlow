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

## Adding a metric

1. Write one function in `metrics_service.py` and document it in the table above.
2. Make every router, export and badge that shows it call that function.
3. Add a test to `test_metrics_consistency.py` that reads it through each screen's API and compares the results.
