"""add currencies, exchange rates, tax rates and purchase order totals

Revision ID: e5b7c9d1f3a2
Revises: d3a8f1c2b9e4
Create Date: 2026-10-26 14:00:00.000000

Existing purchase orders are backfilled in the company's base currency at rate 1, with totals computed from
their lines, so nothing an installation already has changes value.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e5b7c9d1f3a2"
down_revision: str | None = "d3a8f1c2b9e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (code, name, symbol, minor units, active). Frozen here so later edits to the app's list never rewrite history.
CURRENCIES = [
    ("USD", "US Dollar", "$", 2, True),
    ("EUR", "Euro", "€", 2, True),
    ("GBP", "Pound Sterling", "£", 2, True),
    ("CAD", "Canadian Dollar", "CA$", 2, True),
    ("CHF", "Swiss Franc", "CHF", 2, True),
    ("SEK", "Swedish Krona", "kr", 2, True),
    ("NOK", "Norwegian Krone", "kr", 2, True),
    ("DKK", "Danish Krone", "kr", 2, True),
    ("PLN", "Polish Zloty", "zł", 2, True),
    ("CZK", "Czech Koruna", "Kč", 2, False),
    ("HUF", "Hungarian Forint", "Ft", 2, False),
    ("RON", "Romanian Leu", "lei", 2, False),
    ("BGN", "Bulgarian Lev", "лв", 2, False),
    ("ISK", "Icelandic Krona", "kr", 0, False),
    ("TRY", "Turkish Lira", "₺", 2, False),
    ("AUD", "Australian Dollar", "A$", 2, False),
    ("NZD", "New Zealand Dollar", "NZ$", 2, False),
    ("MXN", "Mexican Peso", "MX$", 2, False),
    ("BRL", "Brazilian Real", "R$", 2, False),
    ("JPY", "Japanese Yen", "¥", 0, False),
    ("CNY", "Chinese Yuan", "¥", 2, False),
    ("HKD", "Hong Kong Dollar", "HK$", 2, False),
    ("SGD", "Singapore Dollar", "S$", 2, False),
    ("KRW", "South Korean Won", "₩", 0, False),
    ("INR", "Indian Rupee", "₹", 2, False),
    ("ZAR", "South African Rand", "R", 2, False),
    ("AED", "UAE Dirham", "AED", 2, False),
    ("SAR", "Saudi Riyal", "SAR", 2, False),
    ("BHD", "Bahraini Dinar", "BHD", 3, False),
    ("KWD", "Kuwaiti Dinar", "KWD", 3, False),
]

# (name, percentage, type, inclusive, reverse charge, region). Editable examples, not tax advice.
TAX_RATES = [
    ("US - California sales tax (sample)", "7.2500", "SALES_TAX", False, False, "US-CA"),
    ("US - New York sales tax (sample)", "4.0000", "SALES_TAX", False, False, "US-NY"),
    ("US - Texas sales tax (sample)", "6.2500", "SALES_TAX", False, False, "US-TX"),
    ("US - Washington sales tax (sample)", "6.5000", "SALES_TAX", False, False, "US-WA"),
    ("UK VAT 20%", "20.0000", "VAT", False, False, "GB"),
    ("Germany VAT 19%", "19.0000", "VAT", False, False, "DE"),
    ("France VAT 20%", "20.0000", "VAT", False, False, "FR"),
    ("Netherlands VAT 21%", "21.0000", "VAT", False, False, "NL"),
    ("EU reverse charge 0%", "0.0000", "VAT", False, True, "EU"),
]

# SQLAlchemy stores an Enum's member names, like the existing po_status type does.
tax_type = postgresql.ENUM("VAT", "SALES_TAX", name="tax_type", create_type=False)


def upgrade() -> None:
    currencies = op.create_table(
        "currencies",
        sa.Column("code", sa.String(length=3), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("symbol", sa.String(length=8), nullable=False),
        sa.Column("minor_units", sa.SmallInteger(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.CheckConstraint("minor_units BETWEEN 0 AND 4", name="ck_currencies_minor_units"),
        sa.PrimaryKeyConstraint("code"),
    )
    op.bulk_insert(
        currencies,
        [
            {"code": code, "name": name, "symbol": symbol, "minor_units": units, "is_active": active}
            for code, name, symbol, units, active in CURRENCIES
        ],
    )

    op.create_table(
        "exchange_rates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("base_currency_code", sa.String(length=3), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("rate", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("rate > 0", name="ck_exchange_rates_rate_positive"),
        sa.CheckConstraint("base_currency_code <> currency_code", name="ck_exchange_rates_distinct_currencies"),
        sa.ForeignKeyConstraint(["base_currency_code"], ["currencies.code"]),
        sa.ForeignKeyConstraint(["currency_code"], ["currencies.code"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "base_currency_code", "currency_code", "effective_date", name="uq_exchange_rates_pair_effective_date"
        ),
    )
    op.create_index(op.f("ix_exchange_rates_base_currency_code"), "exchange_rates", ["base_currency_code"])
    op.create_index(op.f("ix_exchange_rates_currency_code"), "exchange_rates", ["currency_code"])
    op.create_index(op.f("ix_exchange_rates_created_by"), "exchange_rates", ["created_by"])

    tax_type.create(op.get_bind(), checkfirst=True)  # type: ignore[no-untyped-call]
    tax_rates = op.create_table(
        "tax_rates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("percentage", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("tax_type", tax_type, nullable=False),
        sa.Column("is_inclusive", sa.Boolean(), nullable=False),
        sa.Column("is_reverse_charge", sa.Boolean(), nullable=False),
        sa.Column("region", sa.String(length=10), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("percentage >= 0 AND percentage <= 100", name="ck_tax_rates_percentage_range"),
        sa.CheckConstraint("NOT is_reverse_charge OR percentage = 0", name="ck_tax_rates_reverse_charge_is_zero"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.bulk_insert(
        tax_rates,
        [
            {
                "name": name,
                "percentage": pct,
                "tax_type": kind,
                "is_inclusive": inclusive,
                "is_reverse_charge": reverse,
                "region": region,
                "is_active": True,
            }
            for name, pct, kind, inclusive, reverse, region in TAX_RATES
        ],
    )

    op.create_foreign_key(
        "fk_company_settings_base_currency", "company_settings", "currencies", ["base_currency_code"], ["code"]
    )
    op.create_index(op.f("ix_company_settings_base_currency_code"), "company_settings", ["base_currency_code"])

    op.add_column("suppliers", sa.Column("country_code", sa.String(length=2), nullable=True))
    op.add_column("suppliers", sa.Column("tax_id", sa.String(length=50), nullable=True))
    op.add_column("suppliers", sa.Column("currency_code", sa.String(length=3), nullable=True))
    op.add_column("suppliers", sa.Column("payment_terms_days", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_suppliers_currency", "suppliers", "currencies", ["currency_code"], ["code"])
    op.create_index(op.f("ix_suppliers_currency_code"), "suppliers", ["currency_code"])

    # Purchase order lines: wider unit price (four decimals) and the tax snapshot, backfilled with no tax.
    op.alter_column(
        "purchase_order_items",
        "unit_price",
        existing_type=sa.Numeric(12, 2),
        type_=sa.Numeric(18, 4),
        existing_nullable=False,
    )
    op.add_column("purchase_order_items", sa.Column("tax_rate_id", sa.Integer(), nullable=True))
    op.add_column("purchase_order_items", sa.Column("tax_name", sa.String(length=100), nullable=True))
    for name, default in (("tax_percent", "0"), ("line_net", "0"), ("line_tax", "0"), ("line_total", "0")):
        precision = (7, 4) if name == "tax_percent" else (18, 4)
        op.add_column(
            "purchase_order_items",
            sa.Column(name, sa.Numeric(*precision), server_default=default, nullable=False),
        )
    for name in ("tax_inclusive", "reverse_charge"):
        op.add_column("purchase_order_items", sa.Column(name, sa.Boolean(), server_default=sa.false(), nullable=False))
    op.create_foreign_key("fk_po_items_tax_rate", "purchase_order_items", "tax_rates", ["tax_rate_id"], ["id"])
    op.create_index(op.f("ix_purchase_order_items_tax_rate_id"), "purchase_order_items", ["tax_rate_id"])
    op.execute("UPDATE purchase_order_items SET line_net = quantity * unit_price, line_total = quantity * unit_price")

    # Purchase orders: currency plus stored totals; committed orders get rate 1 in the base currency.
    op.add_column("purchase_orders", sa.Column("currency_code", sa.String(length=3), nullable=True))
    for name in ("subtotal", "tax_total", "grand_total"):
        op.add_column("purchase_orders", sa.Column(name, sa.Numeric(18, 4), server_default="0", nullable=False))
    op.add_column("purchase_orders", sa.Column("exchange_rate", sa.Numeric(18, 8), nullable=True))
    for name in ("base_subtotal", "base_tax_total", "base_grand_total"):
        op.add_column("purchase_orders", sa.Column(name, sa.Numeric(18, 4), nullable=True))
    op.execute("UPDATE purchase_orders SET currency_code = (SELECT base_currency_code FROM company_settings)")
    op.execute(
        "UPDATE purchase_orders po SET subtotal = t.total, grand_total = t.total FROM ("
        "SELECT po_id, SUM(line_total) AS total FROM purchase_order_items GROUP BY po_id) t WHERE t.po_id = po.id"
    )
    op.execute(
        "UPDATE purchase_orders SET exchange_rate = 1, base_subtotal = subtotal, base_tax_total = tax_total, "
        "base_grand_total = grand_total "
        "WHERE status IN ('APPROVED', 'ORDERED', 'PARTIALLY_RECEIVED', 'RECEIVED')"
    )
    op.alter_column("purchase_orders", "currency_code", nullable=False)
    op.create_foreign_key("fk_purchase_orders_currency", "purchase_orders", "currencies", ["currency_code"], ["code"])
    op.create_index(op.f("ix_purchase_orders_currency_code"), "purchase_orders", ["currency_code"])


def downgrade() -> None:
    op.drop_index(op.f("ix_purchase_orders_currency_code"), table_name="purchase_orders")
    op.drop_constraint("fk_purchase_orders_currency", "purchase_orders", type_="foreignkey")
    for name in (
        "base_grand_total",
        "base_tax_total",
        "base_subtotal",
        "exchange_rate",
        "grand_total",
        "tax_total",
        "subtotal",
        "currency_code",
    ):
        op.drop_column("purchase_orders", name)

    op.drop_index(op.f("ix_purchase_order_items_tax_rate_id"), table_name="purchase_order_items")
    op.drop_constraint("fk_po_items_tax_rate", "purchase_order_items", type_="foreignkey")
    for name in (
        "reverse_charge",
        "tax_inclusive",
        "line_total",
        "line_tax",
        "line_net",
        "tax_percent",
        "tax_name",
        "tax_rate_id",
    ):
        op.drop_column("purchase_order_items", name)
    # Narrowing rounds any sub-cent unit price; only a rollback after four-decimal prices were entered loses detail.
    op.alter_column(
        "purchase_order_items",
        "unit_price",
        existing_type=sa.Numeric(18, 4),
        type_=sa.Numeric(12, 2),
        existing_nullable=False,
    )

    op.drop_index(op.f("ix_suppliers_currency_code"), table_name="suppliers")
    op.drop_constraint("fk_suppliers_currency", "suppliers", type_="foreignkey")
    for name in ("payment_terms_days", "currency_code", "tax_id", "country_code"):
        op.drop_column("suppliers", name)

    op.drop_index(op.f("ix_company_settings_base_currency_code"), table_name="company_settings")
    op.drop_constraint("fk_company_settings_base_currency", "company_settings", type_="foreignkey")
    op.drop_table("tax_rates")
    tax_type.drop(op.get_bind(), checkfirst=True)  # type: ignore[no-untyped-call]
    op.drop_index(op.f("ix_exchange_rates_created_by"), table_name="exchange_rates")
    op.drop_index(op.f("ix_exchange_rates_currency_code"), table_name="exchange_rates")
    op.drop_index(op.f("ix_exchange_rates_base_currency_code"), table_name="exchange_rates")
    op.drop_table("exchange_rates")
    op.drop_table("currencies")
