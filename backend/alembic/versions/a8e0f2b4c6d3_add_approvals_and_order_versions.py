"""add approval rules, steps, delegations, limits and purchase order versions

Revision ID: a8e0f2b4c6d3
Revises: f6c8d0e2a4b1
Create Date: 2026-10-26 18:10:00.000000

Orders already waiting for approval get no steps here: the approval engine opens a single open step for them the
first time someone decides, which is exactly how they were approved before rules existed.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a8e0f2b4c6d3"
down_revision: str | None = "f6c8d0e2a4b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

approval_document_type = postgresql.ENUM(
    "PURCHASE_REQUEST",
    "PURCHASE_ORDER",
    "PURCHASE_ORDER_AMENDMENT",
    "INVOICE_EXCEPTION",
    name="approval_document_type",
    create_type=False,
)
approval_step_status = postgresql.ENUM(
    "PENDING", "APPROVED", "REJECTED", "SKIPPED", name="approval_step_status", create_type=False
)
amendment_status = postgresql.ENUM(
    "APPLIED", "PENDING_APPROVAL", "REJECTED", name="amendment_status", create_type=False
)
ENUMS = (approval_document_type, approval_step_status, amendment_status)


def _now(name: str = "created_at") -> sa.Column:  # type: ignore[type-arg]
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)


def upgrade() -> None:
    bind = op.get_bind()
    for enum in ENUMS:
        enum.create(bind, checkfirst=True)  # type: ignore[no-untyped-call]

    op.create_table(
        "approval_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("document_type", approval_document_type, nullable=False),
        sa.Column("min_amount", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("max_amount", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        _now(),
        _now("updated_at"),
        sa.CheckConstraint("max_amount IS NULL OR max_amount > min_amount", name="ck_approval_rules_band_is_not_empty"),
        sa.CheckConstraint("min_amount >= 0", name="ck_approval_rules_min_amount_non_negative"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_approval_rules_document_type"), "approval_rules", ["document_type"])

    op.create_table(
        "approval_rule_steps",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("rule_id", sa.Integer(), nullable=False),
        sa.Column("step_order", sa.SmallInteger(), nullable=False),
        sa.Column("approver_role_id", sa.Integer(), nullable=False),
        sa.CheckConstraint("step_order >= 1", name="ck_approval_rule_steps_order_positive"),
        sa.ForeignKeyConstraint(["rule_id"], ["approval_rules.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["approver_role_id"], ["roles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rule_id", "step_order", name="uq_approval_rule_steps_rule_id_step_order"),
    )
    op.create_index(op.f("ix_approval_rule_steps_rule_id"), "approval_rule_steps", ["rule_id"])
    op.create_index(op.f("ix_approval_rule_steps_approver_role_id"), "approval_rule_steps", ["approver_role_id"])

    op.create_table(
        "approval_steps",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_type", approval_document_type, nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("round", sa.SmallInteger(), nullable=False),
        sa.Column("step_order", sa.SmallInteger(), nullable=False),
        sa.Column("approver_role_id", sa.Integer(), nullable=True),
        sa.Column("required_permission", sa.String(length=100), nullable=True),
        sa.Column("rule_id", sa.Integer(), nullable=True),
        sa.Column("rule_name", sa.String(length=150), nullable=True),
        sa.Column("amount_base", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("status", approval_step_status, nullable=False),
        sa.Column("decided_by", sa.Integer(), nullable=True),
        sa.Column("on_behalf_of", sa.Integer(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("comment", sa.String(length=500), nullable=True),
        _now(),
        sa.CheckConstraint(
            "approver_role_id IS NOT NULL OR required_permission IS NOT NULL", name="ck_approval_steps_has_approver"
        ),
        sa.ForeignKeyConstraint(["approver_role_id"], ["roles.id"]),
        sa.ForeignKeyConstraint(["rule_id"], ["approval_rules.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["decided_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["on_behalf_of"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_type", "document_id", "round", "step_order", name="uq_approval_steps_document_round_step"
        ),
    )
    op.create_index("ix_approval_steps_document", "approval_steps", ["document_type", "document_id"])
    for column in ("approver_role_id", "rule_id", "status", "decided_by", "on_behalf_of"):
        op.create_index(op.f(f"ix_approval_steps_{column}"), "approval_steps", [column])

    op.create_table(
        "approval_delegations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("delegator_id", sa.Integer(), nullable=False),
        sa.Column("delegate_id", sa.Integer(), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        _now(),
        sa.CheckConstraint("delegator_id <> delegate_id", name="ck_approval_delegations_distinct_people"),
        sa.CheckConstraint("ends_on >= starts_on", name="ck_approval_delegations_dates_in_order"),
        sa.ForeignKeyConstraint(["delegator_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["delegate_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("delegator_id", "delegate_id", "created_by"):
        op.create_index(op.f(f"ix_approval_delegations_{column}"), "approval_delegations", [column])

    op.create_table(
        "approval_limits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("document_type", approval_document_type, nullable=False),
        sa.Column("max_amount", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("updated_by", sa.Integer(), nullable=False),
        _now("updated_at"),
        sa.CheckConstraint("max_amount >= 0", name="ck_approval_limits_amount_non_negative"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "document_type", name="uq_approval_limits_user_document_type"),
    )
    op.create_index(op.f("ix_approval_limits_user_id"), "approval_limits", ["user_id"])
    op.create_index(op.f("ix_approval_limits_updated_by"), "approval_limits", ["updated_by"])

    op.create_table(
        "purchase_order_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("po_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", amendment_status, nullable=False),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),  # type: ignore[no-untyped-call]
        sa.Column("changes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),  # type: ignore[no-untyped-call]
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        _now(),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["po_id"], ["purchase_orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("po_id", "version", name="uq_purchase_order_versions_po_id_version"),
    )
    op.create_index(op.f("ix_purchase_order_versions_po_id"), "purchase_order_versions", ["po_id"])
    op.create_index(op.f("ix_purchase_order_versions_created_by"), "purchase_order_versions", ["created_by"])


def downgrade() -> None:
    op.drop_table("purchase_order_versions")
    op.drop_table("approval_limits")
    op.drop_table("approval_delegations")
    op.drop_table("approval_steps")
    op.drop_table("approval_rule_steps")
    op.drop_table("approval_rules")
    bind = op.get_bind()
    for enum in reversed(ENUMS):
        enum.drop(bind, checkfirst=True)  # type: ignore[no-untyped-call]
