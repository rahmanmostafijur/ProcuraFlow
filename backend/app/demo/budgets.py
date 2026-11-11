"""Seed step 8: set each cost centre's budget from what it actually spent, so the screens show every health state.

Budgets start as a placeholder (see app.demo.setup). Once the year's orders exist, the application itself reports the
spent and committed amounts per cost centre; this step then sets the budget that makes the utilisation hit the
cost centre's target: healthy ones well below the warning level, near-limit ones just under 100% and one over it.
"""

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.demo.api import DemoApi
from app.demo.catalog import COST_CENTRES

ROUNDING_STEP = Decimal(100)
PRIOR_YEAR_TARGET_PERCENT = 76
FALLBACK_BUDGET = "25000.00"


def budget_for(used: Decimal, target_percent: int) -> Decimal:
    """The budget (to the nearest hundred) at which ``used`` is ``target_percent`` of it."""
    exact = used * 100 / target_percent
    return (exact / ROUNDING_STEP).quantize(Decimal(1), rounding=ROUND_HALF_UP) * ROUNDING_STEP


async def _set(api: DemoApi, position: dict[str, Any], amount: str, reason: str) -> None:
    await api.put(
        "finance",
        "/budgets",
        {
            "cost_centre_id": position["cost_centre_id"],
            "fiscal_year": position["fiscal_year"],
            "amount": amount,
            "reason": reason,
        },
    )


async def tune_budgets(api: DemoApi, fiscal_year: int) -> None:
    targets = {centre.code: centre.target_percent for centre in COST_CENTRES}
    for year, reason in ((fiscal_year - 1, "Year-end review"), (fiscal_year, "Mid-year review")):
        for position in await api.get("finance", "/budgets", params={"fiscal_year": year}):
            used = Decimal(position["spent"]) + Decimal(position["committed"])
            if used <= 0:
                await _set(api, position, FALLBACK_BUDGET, reason)
                continue
            percent = targets[position["cost_centre_code"]] if year == fiscal_year else PRIOR_YEAR_TARGET_PERCENT
            await _set(api, position, str(budget_for(used, percent)), reason)
