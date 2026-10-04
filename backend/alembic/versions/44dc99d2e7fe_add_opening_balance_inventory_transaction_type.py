"""add opening balance inventory transaction type

Revision ID: 44dc99d2e7fe
Revises: 65306c803378
Create Date: 2026-10-05 03:17:57.138603

"""
from typing import Sequence, Union

from alembic import op


revision: str = '44dc99d2e7fe'
down_revision: Union[str, None] = '65306c803378'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # A new enum value cannot be used in the transaction that adds it, so commit it on its own.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE inventory_transaction_type ADD VALUE IF NOT EXISTS 'OPENING_BALANCE'")


def downgrade() -> None:
    # PostgreSQL cannot drop an enum value. Leaving it is harmless: older code never writes it.
    pass
