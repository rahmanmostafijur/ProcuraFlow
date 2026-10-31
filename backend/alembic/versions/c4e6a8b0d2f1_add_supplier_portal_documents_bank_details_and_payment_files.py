"""add supplier portal accounts, documents, bank details, payment files and payer details

Revision ID: c4e6a8b0d2f1
Revises: a1c3e5f7b9d2
Create Date: 2026-11-01 09:00:00.000000

Purely additive: new tables and nullable columns. Nothing existing is altered, dropped or rewritten, so the
downgrade only removes what this revision added.
"""

from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision: str = "c4e6a8b0d2f1"
down_revision: str | None = "a1c3e5f7b9d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PAYER_COLUMNS = (
    ("payer_iban", 34),
    ("payer_bic", 11),
    ("payer_routing_number", 9),
    ("payer_account_number", 34),
    ("ach_company_id", 10),
)


def _created_at() -> sa.Column[datetime]:
    return sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now())


def upgrade() -> None:
    op.add_column("users", sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id")))
    op.create_index("ix_users_supplier_id", "users", ["supplier_id"])

    op.add_column("purchase_orders", sa.Column("acknowledged_at", sa.DateTime(timezone=True)))
    op.add_column("purchase_orders", sa.Column("acknowledged_by", sa.Integer(), sa.ForeignKey("users.id")))
    op.create_index("ix_purchase_orders_acknowledged_by", "purchase_orders", ["acknowledged_by"])

    for name, length in PAYER_COLUMNS:
        op.add_column("company_settings", sa.Column(name, sa.String(length)))

    op.create_table(
        "supplier_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("document_type", sa.String(30), nullable=False),
        sa.Column("issue_date", sa.Date()),
        sa.Column("expiry_date", sa.Date()),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(255), nullable=False, unique=True),
        sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        _created_at(),
        sa.CheckConstraint("size_bytes > 0", name="ck_supplier_documents_size_positive"),
        sa.CheckConstraint(
            "issue_date IS NULL OR expiry_date IS NULL OR expiry_date >= issue_date",
            name="ck_supplier_documents_dates_in_order",
        ),
        sa.CheckConstraint(
            "document_type IN ('w9', 'vat_certificate', 'insurance', 'iso_certificate', 'bank_letter')",
            name="ck_supplier_documents_type",
        ),
    )
    op.create_index("ix_supplier_documents_supplier_id", "supplier_documents", ["supplier_id"])
    op.create_index("ix_supplier_documents_uploaded_by", "supplier_documents", ["uploaded_by"])
    op.create_index("ix_supplier_documents_expiry_date", "supplier_documents", ["expiry_date"])

    op.create_table(
        "supplier_bank_details",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("bank_account_name", sa.String(140)),
        sa.Column("iban", sa.String(34)),
        sa.Column("bic", sa.String(11)),
        sa.Column("bank_account_number", sa.String(34)),
        sa.Column("routing_number", sa.String(9)),
        sa.Column("bank_country", sa.String(2)),
        sa.Column("requested_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("decided_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("decision_comment", sa.String(500)),
        sa.Column("superseded_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('pending', 'current', 'superseded', 'rejected')", name="ck_supplier_bank_details_status"
        ),
    )
    op.create_index("ix_supplier_bank_details_supplier_id", "supplier_bank_details", ["supplier_id"])
    op.create_index("ix_supplier_bank_details_requested_by", "supplier_bank_details", ["requested_by"])
    op.create_index("ix_supplier_bank_details_decided_by", "supplier_bank_details", ["decided_by"])
    for status in ("current", "pending"):
        op.create_index(
            f"uq_supplier_bank_details_{status}",
            "supplier_bank_details",
            ["supplier_id"],
            unique=True,
            postgresql_where=sa.text(f"status = '{status}'"),
        )

    op.create_table(
        "payment_run_files",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("payment_runs.id"), nullable=False, unique=True),
        sa.Column("file_format", sa.String(20), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(255), nullable=False, unique=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        _created_at(),
        sa.CheckConstraint("file_format IN ('sepa_pain001', 'nacha_ach')", name="ck_payment_run_files_format"),
        sa.CheckConstraint("size_bytes > 0", name="ck_payment_run_files_size_positive"),
    )
    op.create_index("ix_payment_run_files_created_by", "payment_run_files", ["created_by"])


def downgrade() -> None:
    op.drop_table("payment_run_files")
    op.drop_table("supplier_bank_details")
    op.drop_table("supplier_documents")
    for name, _ in reversed(PAYER_COLUMNS):
        op.drop_column("company_settings", name)
    op.drop_index("ix_purchase_orders_acknowledged_by", table_name="purchase_orders")
    op.drop_column("purchase_orders", "acknowledged_by")
    op.drop_column("purchase_orders", "acknowledged_at")
    op.drop_index("ix_users_supplier_id", table_name="users")
    op.drop_column("users", "supplier_id")
