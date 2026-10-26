"""add goods receipts, supplier returns, supplier invoices, payments and payment runs

Revision ID: b7d1f3a5c9e2
Revises: a8e0f2b4c6d3
Create Date: 2026-10-26 19:00:00.000000

Nothing existing changes meaning. Units already received on an order count as accepted (they were: nothing could be
rejected before), so three-way matching treats them that way. The company setting for matching starts as three-way.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b7d1f3a5c9e2"
down_revision: str | None = "a8e0f2b4c6d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PAYMENT_RUN_NUMBER_SEQUENCE = "payment_run_number_seq"

# SQLAlchemy stores an Enum's member names, like the existing po_status type does.
goods_receipt_condition = postgresql.ENUM(
    "GOOD", "DAMAGED", "WRONG_ITEM", "OTHER", name="goods_receipt_condition", create_type=False
)
return_resolution = postgresql.ENUM("REPLACE", "CREDIT_NOTE", "REPAIR", name="return_resolution", create_type=False)
return_status = postgresql.ENUM("OPEN", "SENT", "RESOLVED", "CANCELLED", name="return_status", create_type=False)
invoice_status = postgresql.ENUM(
    "DRAFT", "MATCHED", "EXCEPTION", "APPROVED", "ON_HOLD", "PAID", "VOID", name="invoice_status", create_type=False
)
invoice_match_mode = postgresql.ENUM("THREE_WAY", "TWO_WAY", name="invoice_match_mode", create_type=False)
payment_method = postgresql.ENUM("BANK_TRANSFER", "CARD", "CHEQUE", name="payment_method", create_type=False)
payment_run_status = postgresql.ENUM("DRAFT", "RELEASED", "CANCELLED", name="payment_run_status", create_type=False)
ENUMS = (
    goods_receipt_condition,
    return_resolution,
    return_status,
    invoice_status,
    invoice_match_mode,
    payment_method,
    payment_run_status,
)


def _now(name: str = "created_at") -> sa.Column:  # type: ignore[type-arg]
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)


def _money(name: str, *, nullable: bool = False) -> sa.Column:  # type: ignore[type-arg]
    return sa.Column(name, sa.Numeric(precision=18, scale=4), nullable=nullable)


def _index(table: str, *columns: str) -> None:
    for column in columns:
        op.create_index(op.f(f"ix_{table}_{column}"), table, [column])


def _create_receipts_and_returns() -> None:
    op.create_table(
        "goods_receipts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("po_id", sa.Integer(), nullable=False),
        sa.Column("received_by", sa.Integer(), nullable=False),
        _now("received_at"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["po_id"], ["purchase_orders.id"]),
        sa.ForeignKeyConstraint(["received_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    _index("goods_receipts", "po_id", "received_by")

    op.create_table(
        "goods_receipt_lines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("receipt_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("delivered_quantity", sa.Integer(), nullable=False),
        sa.Column("accepted_quantity", sa.Integer(), nullable=False),
        sa.Column("rejected_quantity", sa.Integer(), nullable=False),
        sa.Column("condition", goods_receipt_condition, nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.CheckConstraint("delivered_quantity > 0", name="ck_goods_receipt_lines_delivered_positive"),
        sa.CheckConstraint("accepted_quantity >= 0", name="ck_goods_receipt_lines_accepted_non_negative"),
        sa.CheckConstraint("rejected_quantity >= 0", name="ck_goods_receipt_lines_rejected_non_negative"),
        sa.CheckConstraint(
            "accepted_quantity + rejected_quantity = delivered_quantity", name="ck_goods_receipt_lines_adds_up"
        ),
        sa.ForeignKeyConstraint(["receipt_id"], ["goods_receipts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    _index("goods_receipt_lines", "receipt_id", "product_id")

    op.create_table(
        "supplier_returns",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("po_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("resolution", return_resolution, nullable=False),
        sa.Column("status", return_status, nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        _now(),
        _now("updated_at"),
        sa.CheckConstraint("quantity > 0", name="ck_supplier_returns_quantity_positive"),
        sa.ForeignKeyConstraint(["po_id"], ["purchase_orders.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    _index("supplier_returns", "po_id", "product_id", "status", "created_by")


def _create_invoices() -> None:
    op.create_table(
        "supplier_invoices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("supplier_id", sa.Integer(), nullable=False),
        sa.Column("po_id", sa.Integer(), nullable=False),
        sa.Column("invoice_number", sa.String(length=100), nullable=False),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        _money("subtotal"),
        _money("tax_total"),
        _money("grand_total"),
        _money("paid_total"),
        sa.Column("status", invoice_status, nullable=False),
        sa.Column("match_mode", invoice_match_mode, nullable=True),
        sa.Column("tolerance_percent", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column(
            "exception_reasons",
            postgresql.JSONB(astext_type=sa.Text()),  # type: ignore[no-untyped-call]
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("hold_reason", sa.String(length=500), nullable=True),
        sa.Column("status_before_hold", invoice_status, nullable=True),
        sa.Column("void_reason", sa.String(length=500), nullable=True),
        sa.Column("rejection_reason", sa.String(length=500), nullable=True),
        sa.Column("exchange_rate", sa.Numeric(precision=18, scale=8), nullable=True),
        _money("base_subtotal", nullable=True),
        _money("base_tax_total", nullable=True),
        _money("base_grand_total", nullable=True),
        _now(),
        _now("updated_at"),
        sa.CheckConstraint("paid_total >= 0", name="ck_supplier_invoices_paid_non_negative"),
        sa.CheckConstraint("paid_total <= grand_total", name="ck_supplier_invoices_paid_within_total"),
        sa.CheckConstraint("grand_total >= 0", name="ck_supplier_invoices_total_non_negative"),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"]),
        sa.ForeignKeyConstraint(["po_id"], ["purchase_orders.id"]),
        sa.ForeignKeyConstraint(["currency_code"], ["currencies.code"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    _index(
        "supplier_invoices",
        "supplier_id",
        "po_id",
        "due_date",
        "currency_code",
        "status",
        "created_by",
        "approved_by",
    )

    op.create_table(
        "supplier_invoice_lines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("invoice_id", sa.Integer(), nullable=False),
        sa.Column("po_item_id", sa.Integer(), nullable=True),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        _money("unit_price"),
        sa.Column("tax_rate_id", sa.Integer(), nullable=True),
        sa.Column("tax_name", sa.String(length=100), nullable=True),
        sa.Column("tax_percent", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("tax_inclusive", sa.Boolean(), nullable=False),
        sa.Column("reverse_charge", sa.Boolean(), nullable=False),
        _money("line_net"),
        _money("line_tax"),
        _money("line_total"),
        sa.CheckConstraint("quantity > 0", name="ck_supplier_invoice_lines_quantity_positive"),
        sa.CheckConstraint("unit_price >= 0", name="ck_supplier_invoice_lines_unit_price_non_negative"),
        sa.ForeignKeyConstraint(["invoice_id"], ["supplier_invoices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["po_item_id"], ["purchase_order_items.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["tax_rate_id"], ["tax_rates.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    _index("supplier_invoice_lines", "invoice_id", "po_item_id", "product_id", "tax_rate_id")


def _create_payments() -> None:
    op.execute(sa.schema.CreateSequence(sa.Sequence(PAYMENT_RUN_NUMBER_SEQUENCE)))
    op.create_table(
        "payment_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("number", sa.String(length=32), nullable=False),
        sa.Column("status", payment_run_status, nullable=False),
        sa.Column("method", payment_method, nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        _money("total"),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("released_by", sa.Integer(), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        _now(),
        sa.CheckConstraint("total >= 0", name="ck_payment_runs_total_non_negative"),
        sa.ForeignKeyConstraint(["currency_code"], ["currencies.code"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["released_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_payment_runs_number"), "payment_runs", ["number"], unique=True)
    _index("payment_runs", "status", "currency_code", "created_by", "released_by")

    op.create_table(
        "payment_run_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("invoice_id", sa.Integer(), nullable=False),
        _money("amount"),
        sa.CheckConstraint("amount > 0", name="ck_payment_run_items_amount_positive"),
        sa.ForeignKeyConstraint(["run_id"], ["payment_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invoice_id"], ["supplier_invoices.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "invoice_id", name="uq_payment_run_items_run_id_invoice_id"),
    )
    _index("payment_run_items", "run_id", "invoice_id")

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("invoice_id", sa.Integer(), nullable=False),
        sa.Column("payment_run_id", sa.Integer(), nullable=True),
        _money("amount"),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("method", payment_method, nullable=False),
        sa.Column("paid_on", sa.Date(), nullable=False),
        sa.Column("reference", sa.String(length=100), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        _now(),
        sa.CheckConstraint("amount > 0", name="ck_payments_amount_positive"),
        sa.ForeignKeyConstraint(["invoice_id"], ["supplier_invoices.id"]),
        sa.ForeignKeyConstraint(["payment_run_id"], ["payment_runs.id"]),
        sa.ForeignKeyConstraint(["currency_code"], ["currencies.code"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    _index("payments", "invoice_id", "payment_run_id", "currency_code", "created_by")


def upgrade() -> None:
    # A new enum value cannot be used in the transaction that adds it, so commit it on its own.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE attachment_parent_type ADD VALUE IF NOT EXISTS 'SUPPLIER_INVOICE'")

    bind = op.get_bind()
    for enum in ENUMS:
        enum.create(bind, checkfirst=True)  # type: ignore[no-untyped-call]

    _create_receipts_and_returns()
    _create_invoices()
    _create_payments()
    op.add_column(
        "company_settings",
        sa.Column("invoice_matching", invoice_match_mode, server_default="THREE_WAY", nullable=False),
    )


def downgrade() -> None:
    # The invoices these files hang off are about to be dropped, and older code cannot read the enum value.
    op.execute("DELETE FROM attachments WHERE parent_type = 'SUPPLIER_INVOICE'")
    op.drop_column("company_settings", "invoice_matching")
    op.drop_table("payments")
    op.drop_table("payment_run_items")
    op.drop_table("payment_runs")
    op.execute(sa.schema.DropSequence(sa.Sequence(PAYMENT_RUN_NUMBER_SEQUENCE)))
    op.drop_table("supplier_invoice_lines")
    op.drop_table("supplier_invoices")
    op.drop_table("supplier_returns")
    op.drop_table("goods_receipt_lines")
    op.drop_table("goods_receipts")

    bind = op.get_bind()
    for enum in reversed(ENUMS):
        enum.drop(bind, checkfirst=True)  # type: ignore[no-untyped-call]
    # PostgreSQL cannot drop an enum value, so attachment_parent_type keeps SUPPLIER_INVOICE. Nothing uses it now.
