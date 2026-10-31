"""Global search behind the command palette.

A group is searched and returned only when the user could already list that entity through its own endpoint, so
search never reveals anything the user cannot reach elsewhere:

| group             | fields matched              | who gets it (mirrors the list endpoint)                    |
|-------------------|-----------------------------|------------------------------------------------------------|
| purchase orders   | po_number, supplier name    | any internal user (GET /purchase-orders)                   |
| purchase requests | request_number, title       | any internal user; own only without request:read_all       |
| supplier invoices | invoice_number, supplier    | invoice:read (GET /supplier-invoices)                      |
| suppliers         | name, email                 | any internal user (GET /suppliers)                         |
| products          | sku, name                   | any internal user (GET /products)                          |
| payment runs      | number                      | invoice:read (GET /payment-runs)                           |

Matching is a case-insensitive substring; ``%``, ``_`` and ``\\`` in the query are escaped so it cannot widen the
match, and every value is a bound parameter. Plain ILIKE is enough at these table sizes, so no trigram index.
Within a group an exact match comes first, then a prefix match, then the most recent record.
"""

from collections.abc import Callable, Sequence
from typing import Any
from urllib.parse import quote

from sqlalchemy import ColumnElement, Row, Select, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.core.deps import has_permission
from app.models.payment import PaymentRun
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_request import PurchaseRequest
from app.models.supplier import Supplier
from app.models.supplier_invoice import SupplierInvoice
from app.models.user import User
from app.schemas.search import SearchGroup, SearchItem, SearchResponse

MIN_QUERY_LENGTH = 2
MAX_QUERY_LENGTH = 100
DEFAULT_LIMIT = 5
MAX_LIMIT = 10

INVOICE_READ = "invoice:read"
REQUEST_READ_ALL = "request:read_all"
SUPPLIER_WRITE = "supplier:write"

type Column = InstrumentedAttribute[str] | InstrumentedAttribute[str | None]


def _match(fields: Sequence[Column], text: str) -> ColumnElement[bool]:
    return or_(*(field.icontains(text, autoescape=True) for field in fields))


def _rank(fields: Sequence[Column], text: str) -> ColumnElement[int]:
    exact = or_(*(func.lower(field) == text.lower() for field in fields))
    prefix = or_(*(field.istartswith(text, autoescape=True) for field in fields))
    return case((exact, 0), (prefix, 1), else_=2)


def _purchase_orders(text: str, limit: int, user: User) -> Select[Any]:
    fields = (PurchaseOrder.po_number, Supplier.name)
    return (
        select(PurchaseOrder.id, PurchaseOrder.po_number, Supplier.name, PurchaseOrder.status)
        .join(Supplier, Supplier.id == PurchaseOrder.supplier_id)
        .where(_match(fields, text))
        .order_by(_rank(fields, text), PurchaseOrder.created_at.desc(), PurchaseOrder.id.desc())
        .limit(limit)
    )


def _purchase_requests(text: str, limit: int, user: User) -> Select[Any]:
    fields = (PurchaseRequest.request_number, PurchaseRequest.title)
    stmt = select(PurchaseRequest.id, PurchaseRequest.request_number, PurchaseRequest.title, PurchaseRequest.status)
    if not has_permission(user, REQUEST_READ_ALL):
        stmt = stmt.where(PurchaseRequest.requester_id == user.id)
    return (
        stmt.where(_match(fields, text))
        .order_by(_rank(fields, text), PurchaseRequest.created_at.desc(), PurchaseRequest.id.desc())
        .limit(limit)
    )


def _invoices(text: str, limit: int, user: User) -> Select[Any]:
    fields = (SupplierInvoice.invoice_number, Supplier.name)
    return (
        select(
            SupplierInvoice.id,
            SupplierInvoice.invoice_number,
            Supplier.name,
            SupplierInvoice.status,
            SupplierInvoice.po_id,
        )
        .join(Supplier, Supplier.id == SupplierInvoice.supplier_id)
        .where(_match(fields, text))
        .order_by(_rank(fields, text), SupplierInvoice.created_at.desc(), SupplierInvoice.id.desc())
        .limit(limit)
    )


def _suppliers(text: str, limit: int, user: User) -> Select[Any]:
    fields = (Supplier.name, Supplier.email)
    return (
        select(Supplier.id, Supplier.name, Supplier.email)
        .where(_match(fields, text))
        .order_by(_rank(fields, text), Supplier.created_at.desc(), Supplier.id.desc())
        .limit(limit)
    )


def _products(text: str, limit: int, user: User) -> Select[Any]:
    fields = (Product.sku, Product.name)
    return (
        select(Product.id, Product.sku, Product.name)
        .where(_match(fields, text))
        .order_by(_rank(fields, text), Product.created_at.desc(), Product.id.desc())
        .limit(limit)
    )


def _payment_runs(text: str, limit: int, user: User) -> Select[Any]:
    fields = (PaymentRun.number,)
    return (
        select(PaymentRun.id, PaymentRun.number, PaymentRun.method, PaymentRun.currency_code, PaymentRun.status)
        .where(_match(fields, text))
        .order_by(_rank(fields, text), PaymentRun.created_at.desc(), PaymentRun.id.desc())
        .limit(limit)
    )


def _po_item(row: Row[Any], user: User) -> SearchItem:
    return SearchItem(id=row[0], title=row[1], subtitle=row[2], status=str(row[3]), url=f"/purchase-orders/{row[0]}")


def _request_item(row: Row[Any], user: User) -> SearchItem:
    return SearchItem(id=row[0], title=row[1], subtitle=row[2], status=str(row[3]), url=f"/requests/{row[0]}")


def _invoice_item(row: Row[Any], user: User) -> SearchItem:
    # There is no invoice page of its own: invoices are handled on their purchase order.
    return SearchItem(id=row[0], title=row[1], subtitle=row[2], status=str(row[3]), url=f"/purchase-orders/{row[4]}")


def _supplier_item(row: Row[Any], user: User) -> SearchItem:
    # The detail page needs supplier:write; everyone else lands on the list narrowed to the name.
    url = f"/suppliers/{row[0]}" if has_permission(user, SUPPLIER_WRITE) else f"/suppliers?search={quote(row[1])}"
    return SearchItem(id=row[0], title=row[1], subtitle=row[2], status=None, url=url)


def _product_item(row: Row[Any], user: User) -> SearchItem:
    return SearchItem(id=row[0], title=row[2], subtitle=row[1], status=None, url=f"/products?search={quote(row[1])}")


def _payment_run_item(row: Row[Any], user: User) -> SearchItem:
    method = str(row[2]).replace("_", " ")
    return SearchItem(id=row[0], title=row[1], subtitle=f"{method}, {row[3]}", status=str(row[4]), url="/payment-runs")


type Builder = Callable[[str, int, User], Select[Any]]
type Mapper = Callable[[Row[Any], User], SearchItem]

# (type, label, permission required or None, query, row mapper); the order here is the order of the groups.
_GROUPS: tuple[tuple[str, str, str | None, Builder, Mapper], ...] = (
    ("purchase_order", "Purchase orders", None, _purchase_orders, _po_item),
    ("purchase_request", "Purchase requests", None, _purchase_requests, _request_item),
    ("supplier_invoice", "Invoices", INVOICE_READ, _invoices, _invoice_item),
    ("supplier", "Suppliers", None, _suppliers, _supplier_item),
    ("product", "Products", None, _products, _product_item),
    ("payment_run", "Payment runs", INVOICE_READ, _payment_runs, _payment_run_item),
)


async def search(db: AsyncSession, user: User, query: str, limit: int) -> SearchResponse:
    """One query per permitted group; groups with no hits are left out."""
    text = query.strip()
    if len(text) < MIN_QUERY_LENGTH:
        return SearchResponse(query=text, groups=[])
    limit = max(1, min(limit, MAX_LIMIT))
    groups: list[SearchGroup] = []
    for group_type, label, permission, build, to_item in _GROUPS:
        if permission is not None and not has_permission(user, permission):
            continue
        rows = (await db.execute(build(text, limit, user))).all()
        if rows:
            groups.append(SearchGroup(type=group_type, label=label, items=[to_item(row, user) for row in rows]))
    return SearchResponse(query=text, groups=groups)
