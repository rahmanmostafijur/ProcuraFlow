"""Seed step 6: supplier compliance documents, open purchase requests and the stock the year leaves behind."""

from datetime import date, timedelta
from typing import Any

from app.demo.api import DemoApi
from app.demo.catalog import PRODUCTS, SUPPLIERS_BY_NAME
from app.demo.setup import Foundation
from app.demo.year import SeedContext

# The smallest file the upload checks accept as a PDF; the content is irrelevant to the demo.
DEMO_PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 10 10]>>endobj\n"
    b"trailer<</Root 1 0 R>>\n%%EOF\n"
)
EXPIRED_DAYS_AGO = 25
EXPIRING_IN_DAYS = 18
STOCK_ADJUSTMENT_REASON = "Issued to departments (year to date)"

# supplier, document type, issued days ago, expires in days (None: no expiry, negative: already expired)
DOCUMENTS: tuple[tuple[str, str, int, int | None], ...] = (
    ("Prairie Office Supply Co.", "w9", 700, None),
    ("Lakeshore Packaging Inc.", "insurance", 245, 120),
    ("Summit Industrial Parts LLC", "insurance", 390, -EXPIRED_DAYS_AGO),
    ("Rheinwerk Elektronik GmbH", "vat_certificate", 125, 240),
    ("Atelier Lumiere SARL", "iso_certificate", 347, EXPIRING_IN_DAYS),
    ("Thames Stationery Ltd", "vat_certificate", 60, 305),
)


async def upload_documents(ctx: SeedContext) -> None:
    """One expired and one expiring document stand out among valid ones on the compliance screen."""
    for supplier, document_type, issued_days_ago, expires_in in DOCUMENTS:
        data: dict[str, str] = {
            "document_type": document_type,
            "issue_date": str(ctx.today - timedelta(days=issued_days_ago)),
        }
        if expires_in is not None:
            data["expiry_date"] = str(ctx.today + timedelta(days=expires_in))
        await ctx.api.call(
            "procurement_manager",
            "POST",
            f"/suppliers/{ctx.foundation.supplier_ids[supplier]}/documents",
            data=data,
            files={"file": (f"{document_type}.pdf", DEMO_PDF, "application/pdf")},
        )


def _request_body(
    foundation: Foundation, title: str, supplier: str, cost_centre: str, needed_by: date, lines: list[dict[str, Any]]
) -> dict[str, Any]:
    spec = SUPPLIERS_BY_NAME[supplier]
    return {
        "title": title,
        "cost_centre_id": foundation.cost_centre_ids[cost_centre],
        "currency_code": spec.currency_code,
        "needed_by": str(needed_by),
        "lines": [{**line, "supplier_id": foundation.supplier_ids[supplier]} for line in lines],
    }


async def open_requests(ctx: SeedContext) -> None:
    """An employee's draft, a request waiting for approval and one that was rejected with a reason."""
    api, foundation, today = ctx.api, ctx.foundation, ctx.today
    monitors = {"description": "27-inch monitor", "quantity": 4, "unit": "unit", "estimated_unit_price": "189.00"}
    draft = _request_body(
        foundation,
        "Spare stretch wrap for the dock",
        "Lakeshore Packaging Inc.",
        "WH",
        today + timedelta(days=20),
        [{"description": "Stretch wrap roll", "quantity": 30, "unit": "roll", "estimated_unit_price": "12.40"}],
    )
    waiting = _request_body(
        foundation,
        "Monitors for the new analysts",
        "Rheinwerk Elektronik GmbH",
        "IT",
        today + timedelta(days=14),
        [{**monitors, "product_id": foundation.product_ids["ELC-4003"]}],
    )
    rejected = _request_body(
        foundation,
        "Standing desk converters",
        "Atelier Lumiere SARL",
        "FAC",
        today + timedelta(days=30),
        [{"description": "Standing desk converter", "quantity": 6, "unit": "unit", "estimated_unit_price": "139.00"}],
    )
    await api.post("employee", "/purchase-requests", draft)
    created = await api.post("employee", "/purchase-requests", waiting)
    await api.post("employee", f"/purchase-requests/{created['id']}/submit")
    created = await api.post("employee", "/purchase-requests", rejected)
    await api.post("employee", f"/purchase-requests/{created['id']}/submit")
    await api.post(
        "department_manager",
        f"/purchase-requests/{created['id']}/reject",
        {"comment": "Not in this year's facilities plan; please resubmit in the new budget round"},
    )


async def settle_stock(api: DemoApi, foundation: Foundation) -> None:
    """Issue stock to departments so each product ends near its planned level; a few end below their minimum.

    The issues are booked as ledger adjustments, so every product's stock still equals the sum of its movements.
    """
    for product in PRODUCTS:
        product_id = foundation.product_ids[product.sku]
        current = (await api.get("warehouse_manager", f"/products/{product_id}"))["current_stock"]
        target = int(product.minimum_stock * product.stock_ratio)
        if current > target:
            await api.post(
                "warehouse_manager",
                "/inventory/adjustments",
                {"product_id": product_id, "quantity_delta": target - current, "reason": STOCK_ADJUSTMENT_REASON},
            )
