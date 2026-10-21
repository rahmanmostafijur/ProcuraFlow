"""add session start to refresh tokens

Revision ID: c7e2a9f4d610
Revises: b1d4e8a27c35
Create Date: 2026-10-19 21:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c7e2a9f4d610"
down_revision: str | None = "b1d4e8a27c35"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Existing rows start their absolute session clock now, which can only lengthen an old session once.
    op.add_column(
        "refresh_tokens",
        sa.Column("family_started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("refresh_tokens", "family_started_at")
