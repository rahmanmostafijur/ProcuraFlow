"""backfill opening balance ledger rows

Revision ID: 1224b37f7c19
Revises: 44dc99d2e7fe
Create Date: 2026-10-05 03:23:17.030032

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '1224b37f7c19'
down_revision: Union[str, None] = '44dc99d2e7fe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BACKFILL_REASON = f"Backfilled opening balance (migration {revision})"

MISMATCHED_PRODUCTS = """
    SELECT product.id AS product_id,
           product.current_stock,
           product.current_stock - COALESCE(SUM(movement.quantity_delta), 0) AS missing_quantity
    FROM products AS product
    LEFT JOIN inventory_transactions AS movement ON movement.product_id = product.id
    GROUP BY product.id, product.current_stock
    HAVING product.current_stock <> COALESCE(SUM(movement.quantity_delta), 0)
"""

EARLIEST_ACTIVE_ADMIN = sa.text(
    """
    SELECT app_user.id
    FROM users AS app_user
    JOIN roles AS role ON role.id = app_user.role_id
    WHERE role.name = 'admin' AND app_user.is_active
    ORDER BY app_user.created_at, app_user.id
    LIMIT 1
    """
)


def _earliest_active_admin_id(bind: sa.engine.Connection) -> int:
    admin_id = bind.execute(EARLIEST_ACTIVE_ADMIN).scalar()
    if admin_id is None:
        raise RuntimeError(
            "Cannot backfill opening balances: some products have stock that is not in the inventory ledger, "
            "and there is no active admin user to record the backfill as (inventory_transactions.created_by is "
            "required). Create or reactivate an admin user, then run the migration again."
        )
    return admin_id


def upgrade() -> None:
    bind = op.get_bind()
    has_mismatches = bind.execute(sa.text(f"SELECT EXISTS ({MISMATCHED_PRODUCTS})")).scalar()
    if not has_mismatches:
        return

    # Earlier movements were never recorded, so history cannot be rebuilt. One reconciliation row per
    # product, stamped now and ending at the current stock, makes stock equal the ledger sum again.
    bind.execute(
        sa.text(
            f"""
            INSERT INTO inventory_transactions
                (product_id, type, quantity_delta, resulting_stock, reason, created_by)
            SELECT mismatch.product_id,
                   'OPENING_BALANCE',
                   mismatch.missing_quantity,
                   mismatch.current_stock,
                   :reason,
                   :created_by
            FROM ({MISMATCHED_PRODUCTS}) AS mismatch
            ORDER BY mismatch.product_id
            """
        ),
        {"reason": BACKFILL_REASON, "created_by": _earliest_active_admin_id(bind)},
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text("DELETE FROM inventory_transactions WHERE type = 'OPENING_BALANCE' AND reason = :reason"),
        {"reason": BACKFILL_REASON},
    )
