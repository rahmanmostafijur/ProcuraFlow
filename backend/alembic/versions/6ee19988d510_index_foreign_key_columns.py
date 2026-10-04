"""index foreign key columns

Revision ID: 6ee19988d510
Revises: 1224b37f7c19
Create Date: 2026-10-05 03:35:54.397473

"""
from typing import Sequence, Union

from alembic import op


revision: str = '6ee19988d510'
down_revision: Union[str, None] = '1224b37f7c19'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Postgres does not index the referencing side of a foreign key, so joins and parent deletes scan these tables.
FOREIGN_KEY_COLUMNS = (
    ("audit_logs", "user_id"),
    ("inventory_transactions", "created_by"),
    ("inventory_transactions", "reference_po_id"),
    ("products", "category_id"),
    ("products", "supplier_id"),
    ("purchase_order_items", "product_id"),
    ("purchase_orders", "approved_by"),
    ("purchase_orders", "created_by"),
    ("purchase_orders", "supplier_id"),
    ("role_permissions", "permission_id"),
    ("users", "role_id"),
)


def upgrade() -> None:
    for table, column in FOREIGN_KEY_COLUMNS:
        op.create_index(op.f(f"ix_{table}_{column}"), table, [column], unique=False)


def downgrade() -> None:
    for table, column in reversed(FOREIGN_KEY_COLUMNS):
        op.drop_index(op.f(f"ix_{table}_{column}"), table_name=table)
