"""add company settings

Revision ID: d3a8f1c2b9e4
Revises: c7e2a9f4d610
Create Date: 2026-10-26 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d3a8f1c2b9e4"
down_revision: str | None = "c7e2a9f4d610"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "company_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_name", sa.String(length=200), nullable=False),
        sa.Column("legal_name", sa.String(length=200), nullable=True),
        sa.Column("address_line1", sa.String(length=200), nullable=True),
        sa.Column("address_line2", sa.String(length=200), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("region", sa.String(length=100), nullable=True),
        sa.Column("postal_code", sa.String(length=20), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=True),
        sa.Column("tax_id", sa.String(length=50), nullable=True),
        sa.Column("contact_email", sa.String(length=255), nullable=True),
        sa.Column("contact_phone", sa.String(length=50), nullable=True),
        sa.Column("logo_storage_key", sa.String(length=255), nullable=True),
        sa.Column("logo_content_type", sa.String(length=50), nullable=True),
        sa.Column("logo_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("brand_color", sa.String(length=7), nullable=False),
        sa.Column("base_currency_code", sa.String(length=3), nullable=False),
        sa.Column("fiscal_year_start_month", sa.SmallInteger(), nullable=False),
        sa.Column("date_format", sa.String(length=10), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("po_number_prefix", sa.String(length=10), nullable=False),
        sa.Column("invoice_tolerance_percent", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("default_payment_terms_days", sa.Integer(), nullable=False),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_company_settings_singleton"),
        sa.CheckConstraint("fiscal_year_start_month BETWEEN 1 AND 12", name="ck_company_settings_fiscal_month"),
        sa.CheckConstraint(
            "invoice_tolerance_percent >= 0 AND invoice_tolerance_percent <= 100",
            name="ck_company_settings_tolerance_range",
        ),
        sa.CheckConstraint("default_payment_terms_days >= 0", name="ck_company_settings_payment_terms"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_company_settings_updated_by"), "company_settings", ["updated_by"], unique=False)
    # The defaults an existing installation starts from; the "PO" prefix keeps its numbering unchanged.
    op.execute(
        "INSERT INTO company_settings (id, company_name, brand_color, base_currency_code, fiscal_year_start_month, "
        "date_format, timezone, po_number_prefix, invoice_tolerance_percent, default_payment_terms_days) "
        "VALUES (1, 'ProcuraFlow', '#0F766E', 'USD', 1, 'MM/DD/YYYY', 'UTC', 'PO', 2.00, 30)"
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_company_settings_updated_by"), table_name="company_settings")
    op.drop_table("company_settings")
