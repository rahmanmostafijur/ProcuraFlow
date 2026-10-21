"""add purchase order number sequence

Revision ID: ebae2c6ec180
Revises: 1046460b0276
Create Date: 2026-10-05 02:45:12.708648

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "ebae2c6ec180"
down_revision: str | None = "1046460b0276"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEQUENCE_NAME = "purchase_order_number_seq"


def upgrade() -> None:
    op.execute(sa.schema.CreateSequence(sa.Sequence(SEQUENCE_NAME)))
    # Continue after the highest number already issued (in any year) so existing POs never collide.
    op.execute(
        f"""
        SELECT setval(
            '{SEQUENCE_NAME}',
            COALESCE(MAX(CAST(substring(po_number FROM '([0-9]+)$') AS bigint)), 0) + 1,
            false
        )
        FROM purchase_orders
        """
    )


def downgrade() -> None:
    op.execute(sa.schema.DropSequence(sa.Sequence(SEQUENCE_NAME)))
