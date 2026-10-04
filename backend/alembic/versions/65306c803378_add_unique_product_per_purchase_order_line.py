"""add unique product per purchase order line

Revision ID: 65306c803378
Revises: ebae2c6ec180
Create Date: 2026-10-05 03:00:55.697936

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '65306c803378'
down_revision: Union[str, None] = 'ebae2c6ec180'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CONSTRAINT_NAME = "uq_purchase_order_items_po_id_product_id"

DUPLICATE_LINES_QUERY = sa.text(
    """
    SELECT po.id AS po_id, po.po_number, item.product_id, COUNT(*) AS line_count
    FROM purchase_order_items AS item
    JOIN purchase_orders AS po ON po.id = item.po_id
    GROUP BY po.id, po.po_number, item.product_id
    HAVING COUNT(*) > 1
    ORDER BY po.id, item.product_id
    """
)


def _ensure_no_duplicate_lines() -> None:
    # Merging lines changes ordered and received quantities, so an operator must decide how; never guess here.
    duplicates = op.get_bind().execute(DUPLICATE_LINES_QUERY).all()
    if not duplicates:
        return
    affected = "\n".join(
        f"  po_id={row.po_id} ({row.po_number}), product_id={row.product_id}: {row.line_count} lines"
        for row in duplicates
    )
    raise RuntimeError(
        f"Cannot add {CONSTRAINT_NAME}: these purchase orders list the same product on more than one line.\n"
        f"{affected}\n"
        "Merge each group into a single line (sum quantity and received_quantity, settle the unit price), "
        "delete the extra lines, then run the migration again."
    )


def upgrade() -> None:
    _ensure_no_duplicate_lines()
    op.create_unique_constraint(CONSTRAINT_NAME, "purchase_order_items", ["po_id", "product_id"])


def downgrade() -> None:
    op.drop_constraint(CONSTRAINT_NAME, "purchase_order_items", type_="unique")
