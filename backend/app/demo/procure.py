"""Seed step 2: ordering and receiving. Purchase requests, purchase orders, approvals, amendments and deliveries."""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Literal

from app.demo.api import DemoApi
from app.demo.catalog import ProductSpec, SupplierSpec
from app.demo.plan import LinePlan, OrderPlan
from app.demo.setup import Foundation

SMALL_ORDER = "procurement_manager"
Until = Literal["draft", "submit", "order"]


@dataclass
class OrderRecord:
    """What the seed knows about one order after creating it; the timeline step later dates it from this."""

    po_id: int
    supplier: SupplierSpec
    order_date: date
    delivery_date: date
    request_id: int | None = None
    received_on: date | None = None
    invoice_ids: tuple[int, ...] = ()


def order_items(foundation: Foundation, supplier: SupplierSpec, lines: tuple[LinePlan, ...]) -> list[dict[str, Any]]:
    tax_id = foundation.tax_ids.get(supplier.tax) if supplier.tax else None
    return [
        {
            "product_id": foundation.product_ids[line.product.sku],
            "quantity": line.quantity,
            "unit_price": str(line.product.price),
            **({"tax_rate_id": tax_id} if tax_id is not None else {}),
        }
        for line in lines
    ]


async def _request_to_order(api: DemoApi, foundation: Foundation, plan: OrderPlan) -> tuple[int, int]:
    """An employee asks, a department manager approves and the purchasing officer turns it into a draft order."""
    supplier = plan.supplier
    request = await api.post(
        "employee",
        "/purchase-requests",
        {
            "title": f"{plan.lines[0].product.name} for {supplier.cost_centre}",
            "cost_centre_id": foundation.cost_centre_ids[supplier.cost_centre],
            "currency_code": supplier.currency_code,
            "needed_by": str(plan.delivery_date),
            "lines": [
                {
                    "description": line.product.name,
                    "quantity": line.quantity,
                    "unit": line.product.unit,
                    "estimated_unit_price": str(line.product.price),
                    "product_id": foundation.product_ids[line.product.sku],
                    "supplier_id": foundation.supplier_ids[supplier.name],
                }
                for line in plan.lines
            ],
        },
    )
    await api.post("employee", f"/purchase-requests/{request['id']}/submit")
    await api.post("department_manager", f"/purchase-requests/{request['id']}/approve", {"comment": "Approved"})
    converted = await api.post(
        "purchasing_officer",
        f"/purchase-requests/{request['id']}/convert",
        {
            "orders": [
                {
                    "supplier_id": foundation.supplier_ids[supplier.name],
                    "lines": [{"line_id": line["id"]} for line in request["lines"]],
                    "expected_delivery_date": str(plan.delivery_date),
                }
            ]
        },
    )
    return converted["purchase_order_ids"][0], request["id"]


async def draft_order(api: DemoApi, foundation: Foundation, plan: OrderPlan) -> tuple[int, int | None]:
    """A draft purchase order, directly or through a request. Returns the order id and the request id."""
    if plan.via_request:
        return await _request_to_order(api, foundation, plan)
    created = await api.post(
        "purchasing_officer",
        "/purchase-orders",
        {
            "supplier_id": foundation.supplier_ids[plan.supplier.name],
            "currency_code": plan.supplier.currency_code,
            "cost_centre_id": foundation.cost_centre_ids[plan.supplier.cost_centre],
            "expected_delivery_date": str(plan.delivery_date),
            "notes": f"Order placed {plan.order_date.isoformat()}",
            "items": order_items(foundation, plan.supplier, plan.lines),
        },
    )
    return created["id"], None


async def approve_order(api: DemoApi, po_id: int, first_approver: str = SMALL_ORDER) -> dict[str, Any]:
    """Decide the order's approval steps: the manager (or the named cover), then finance when the rule needs it."""
    po = await api.post(first_approver, f"/purchase-orders/{po_id}/approve", {"comment": "Approved"})
    if po["status"] == "submitted":
        po = await api.post("finance", f"/purchase-orders/{po_id}/approve", {"comment": "Approved by finance"})
    return po  # type: ignore[no-any-return]


async def place_order(api: DemoApi, po_id: int) -> dict[str, Any]:
    return await api.post("purchasing_officer", f"/purchase-orders/{po_id}/order")  # type: ignore[no-any-return]


async def receive(
    api: DemoApi, po_id: int, deliveries: list[tuple[ProductSpec, int, int]], foundation: Foundation, note: str
) -> dict[str, Any]:
    """Book one delivery. Each entry is (product, units that arrived, units rejected)."""
    items = [
        {
            "product_id": foundation.product_ids[product.sku],
            "quantity": arrived,
            "rejected_quantity": rejected,
            "condition": "damaged" if rejected else "good",
        }
        for product, arrived, rejected in deliveries
    ]
    return await api.post(  # type: ignore[no-any-return]
        "warehouse_manager", f"/purchase-orders/{po_id}/receive", {"items": items, "note": note}
    )


def receipt_date(plan: OrderPlan, today: date, delay_days: int) -> date:
    return min(plan.delivery_date + timedelta(days=delay_days), today)


async def advance_order(api: DemoApi, foundation: Foundation, plan: OrderPlan, until: Until = "order") -> OrderRecord:
    """Create the order and take it as far as ``until``: left as a draft, waiting for approval, or placed."""
    po_id, request_id = await draft_order(api, foundation, plan)
    record = OrderRecord(po_id, plan.supplier, plan.order_date, plan.delivery_date, request_id)
    if until == "draft":
        return record
    await api.post("purchasing_officer", f"/purchase-orders/{po_id}/submit")
    if until == "submit":
        return record
    await approve_order(api, po_id)
    await place_order(api, po_id)
    return record
