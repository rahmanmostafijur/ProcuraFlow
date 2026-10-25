"""add budgets, catalog, attachments and purchase requests

Revision ID: f6c8d0e2a4b1
Revises: e5b7c9d1f3a2
Create Date: 2026-10-26 18:00:00.000000

Existing purchase orders keep working untouched: the new order columns are empty (no cost centre, no source
request) and version 1, and the budget rules start switched off.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f6c8d0e2a4b1"
down_revision: str | None = "e5b7c9d1f3a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REQUEST_NUMBER_SEQUENCE = "purchase_request_number_seq"

# SQLAlchemy stores an Enum's member names, like the existing po_status type does.
purchase_request_status = postgresql.ENUM(
    "DRAFT",
    "SUBMITTED",
    "APPROVED",
    "REJECTED",
    "CONVERTED",
    "CANCELLED",
    name="purchase_request_status",
    create_type=False,
)
budget_transfer_status = postgresql.ENUM(
    "PENDING", "APPROVED", "REJECTED", name="budget_transfer_status", create_type=False
)
budget_change_type = postgresql.ENUM(
    "CREATED", "ADJUSTED", "TRANSFER_IN", "TRANSFER_OUT", name="budget_change_type", create_type=False
)
attachment_parent_type = postgresql.ENUM(
    "PURCHASE_REQUEST", "PURCHASE_ORDER", name="attachment_parent_type", create_type=False
)
ENUMS = (purchase_request_status, budget_transfer_status, budget_change_type, attachment_parent_type)


def _now() -> sa.Column:  # type: ignore[type-arg]
    return sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)


def upgrade() -> None:
    bind = op.get_bind()
    for enum in ENUMS:
        enum.create(bind, checkfirst=True)  # type: ignore[no-untyped-call]
    op.execute(sa.schema.CreateSequence(sa.Sequence(REQUEST_NUMBER_SEQUENCE)))

    op.create_table(
        "cost_centres",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("manager_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        _now(),
        sa.ForeignKeyConstraint(["manager_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(op.f("ix_cost_centres_manager_id"), "cost_centres", ["manager_id"])

    op.create_table(
        "budgets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cost_centre_id", sa.Integer(), nullable=False),
        sa.Column("fiscal_year", sa.SmallInteger(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=4), nullable=False),
        _now(),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("amount >= 0", name="ck_budgets_amount_non_negative"),
        sa.ForeignKeyConstraint(["cost_centre_id"], ["cost_centres.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cost_centre_id", "fiscal_year", name="uq_budgets_cost_centre_fiscal_year"),
    )
    op.create_index(op.f("ix_budgets_cost_centre_id"), "budgets", ["cost_centre_id"])

    op.create_table(
        "budget_transfers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("from_budget_id", sa.Integer(), nullable=False),
        sa.Column("to_budget_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("status", budget_transfer_status, nullable=False),
        sa.Column("requested_by", sa.Integer(), nullable=False),
        sa.Column("decided_by", sa.Integer(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_comment", sa.String(length=500), nullable=True),
        _now(),
        sa.CheckConstraint("amount > 0", name="ck_budget_transfers_amount_positive"),
        sa.CheckConstraint("from_budget_id <> to_budget_id", name="ck_budget_transfers_distinct_budgets"),
        sa.ForeignKeyConstraint(["from_budget_id"], ["budgets.id"]),
        sa.ForeignKeyConstraint(["to_budget_id"], ["budgets.id"]),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["decided_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("from_budget_id", "to_budget_id", "requested_by", "decided_by", "status"):
        op.create_index(op.f(f"ix_budget_transfers_{column}"), "budget_transfers", [column])

    op.create_table(
        "budget_changes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("budget_id", sa.Integer(), nullable=False),
        sa.Column("change_type", budget_change_type, nullable=False),
        sa.Column("old_amount", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("new_amount", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("transfer_id", sa.Integer(), nullable=True),
        sa.Column("changed_by", sa.Integer(), nullable=False),
        _now(),
        sa.ForeignKeyConstraint(["budget_id"], ["budgets.id"]),
        sa.ForeignKeyConstraint(["transfer_id"], ["budget_transfers.id"]),
        sa.ForeignKeyConstraint(["changed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("budget_id", "transfer_id", "changed_by"):
        op.create_index(op.f(f"ix_budget_changes_{column}"), "budget_changes", [column])

    op.create_table(
        "catalog_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("supplier_id", sa.Integer(), nullable=False),
        sa.Column("contract_price", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("lead_time_days", sa.SmallInteger(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        _now(),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("contract_price >= 0", name="ck_catalog_items_price_non_negative"),
        sa.CheckConstraint("lead_time_days >= 0", name="ck_catalog_items_lead_time_non_negative"),
        sa.CheckConstraint(
            "valid_until IS NULL OR valid_from IS NULL OR valid_until >= valid_from", name="ck_catalog_items_dates"
        ),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"]),
        sa.ForeignKeyConstraint(["currency_code"], ["currencies.code"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "product_id", "supplier_id", "currency_code", name="uq_catalog_items_product_supplier_currency"
        ),
    )
    for column in ("product_id", "supplier_id", "currency_code"):
        op.create_index(op.f(f"ix_catalog_items_{column}"), "catalog_items", [column])

    op.create_table(
        "attachments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("parent_type", attachment_parent_type, nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("uploaded_by", sa.Integer(), nullable=False),
        _now(),
        sa.CheckConstraint("size_bytes > 0", name="ck_attachments_size_positive"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index("ix_attachments_parent", "attachments", ["parent_type", "parent_id"])
    op.create_index(op.f("ix_attachments_uploaded_by"), "attachments", ["uploaded_by"])

    op.create_table(
        "purchase_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("request_number", sa.String(length=32), nullable=False),
        sa.Column("requester_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("cost_centre_id", sa.Integer(), nullable=True),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("needed_by", sa.Date(), nullable=True),
        sa.Column("status", purchase_request_status, nullable=False),
        sa.Column("estimated_total", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("base_estimated_total", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.String(length=500), nullable=True),
        _now(),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["requester_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["cost_centre_id"], ["cost_centres.id"]),
        sa.ForeignKeyConstraint(["currency_code"], ["currencies.code"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_purchase_requests_request_number"), "purchase_requests", ["request_number"], unique=True)
    for column in ("requester_id", "cost_centre_id", "currency_code", "status"):
        op.create_index(op.f(f"ix_purchase_requests_{column}"), "purchase_requests", [column])

    op.create_table(
        "purchase_request_lines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("catalog_item_id", sa.Integer(), nullable=True),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("supplier_id", sa.Integer(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column("estimated_unit_price", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("line_total", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("converted_po_id", sa.Integer(), nullable=True),
        sa.CheckConstraint("estimated_unit_price >= 0", name="ck_purchase_request_lines_price_non_negative"),
        sa.CheckConstraint("quantity > 0", name="ck_purchase_request_lines_quantity_positive"),
        sa.ForeignKeyConstraint(["request_id"], ["purchase_requests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["catalog_item_id"], ["catalog_items.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"]),
        sa.ForeignKeyConstraint(["converted_po_id"], ["purchase_orders.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("request_id", "catalog_item_id", "product_id", "supplier_id", "converted_po_id"):
        op.create_index(op.f(f"ix_purchase_request_lines_{column}"), "purchase_request_lines", [column])

    op.add_column("purchase_orders", sa.Column("cost_centre_id", sa.Integer(), nullable=True))
    op.add_column("purchase_orders", sa.Column("purchase_request_id", sa.Integer(), nullable=True))
    op.add_column("purchase_orders", sa.Column("version", sa.Integer(), server_default="1", nullable=False))
    op.create_foreign_key(
        "fk_purchase_orders_cost_centre", "purchase_orders", "cost_centres", ["cost_centre_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_purchase_orders_purchase_request", "purchase_orders", "purchase_requests", ["purchase_request_id"], ["id"]
    )
    op.create_index(op.f("ix_purchase_orders_cost_centre_id"), "purchase_orders", ["cost_centre_id"])
    op.create_index(op.f("ix_purchase_orders_purchase_request_id"), "purchase_orders", ["purchase_request_id"])

    op.add_column(
        "company_settings",
        sa.Column("budget_block_over_budget", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "company_settings",
        sa.Column("budget_warn_percent", sa.Numeric(precision=5, scale=2), server_default="80", nullable=False),
    )
    op.create_check_constraint(
        "ck_company_settings_budget_warn_range",
        "company_settings",
        "budget_warn_percent >= 0 AND budget_warn_percent <= 100",
    )


def downgrade() -> None:
    op.drop_constraint("ck_company_settings_budget_warn_range", "company_settings", type_="check")
    op.drop_column("company_settings", "budget_warn_percent")
    op.drop_column("company_settings", "budget_block_over_budget")

    op.drop_index(op.f("ix_purchase_orders_purchase_request_id"), table_name="purchase_orders")
    op.drop_index(op.f("ix_purchase_orders_cost_centre_id"), table_name="purchase_orders")
    op.drop_constraint("fk_purchase_orders_purchase_request", "purchase_orders", type_="foreignkey")
    op.drop_constraint("fk_purchase_orders_cost_centre", "purchase_orders", type_="foreignkey")
    op.drop_column("purchase_orders", "version")
    op.drop_column("purchase_orders", "purchase_request_id")
    op.drop_column("purchase_orders", "cost_centre_id")

    op.drop_table("purchase_request_lines")
    op.drop_table("purchase_requests")
    op.drop_table("attachments")
    op.drop_table("catalog_items")
    op.drop_table("budget_changes")
    op.drop_table("budget_transfers")
    op.drop_table("budgets")
    op.drop_table("cost_centres")

    op.execute(sa.schema.DropSequence(sa.Sequence(REQUEST_NUMBER_SEQUENCE)))
    bind = op.get_bind()
    for enum in reversed(ENUMS):
        enum.drop(bind, checkfirst=True)  # type: ignore[no-untyped-call]
