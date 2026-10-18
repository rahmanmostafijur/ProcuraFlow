"""add login failures

Revision ID: b1d4e8a27c35
Revises: 9f3a1c7d2b84
Create Date: 2026-10-19 21:10:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'b1d4e8a27c35'
down_revision: Union[str, None] = '9f3a1c7d2b84'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'login_failures',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('scope', sa.String(length=16), nullable=False),
        sa.Column('key_hash', sa.String(length=64), nullable=False),
        sa.Column('failed_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_login_failures_scope_key_failed_at', 'login_failures', ['scope', 'key_hash', 'failed_at'], unique=False)
    op.create_index(op.f('ix_login_failures_failed_at'), 'login_failures', ['failed_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_login_failures_failed_at'), table_name='login_failures')
    op.drop_index('ix_login_failures_scope_key_failed_at', table_name='login_failures')
    op.drop_table('login_failures')
