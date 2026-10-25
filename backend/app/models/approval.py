from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import ApprovalDocumentType, ApprovalStepStatus

if TYPE_CHECKING:
    from app.models.user import User


class ApprovalRule(Base):
    """Who must approve a kind of document, chosen by the document's amount in the base currency.

    A rule applies to amounts from ``min_amount`` (inclusive) up to ``max_amount`` (exclusive; empty means no upper
    limit). Its steps are copied onto a document when it is submitted, so editing a rule later never changes a
    document that is already waiting for approval.
    """

    __tablename__ = "approval_rules"
    __table_args__ = (
        CheckConstraint("min_amount >= 0", name="ck_approval_rules_min_amount_non_negative"),
        CheckConstraint("max_amount IS NULL OR max_amount > min_amount", name="ck_approval_rules_band_is_not_empty"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    document_type: Mapped[ApprovalDocumentType] = mapped_column(
        SAEnum(ApprovalDocumentType, name="approval_document_type"), nullable=False, index=True
    )
    min_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    max_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    steps: Mapped[list["ApprovalRuleStep"]] = relationship(
        back_populates="rule", cascade="all, delete-orphan", order_by="ApprovalRuleStep.step_order"
    )


class ApprovalRuleStep(Base):
    __tablename__ = "approval_rule_steps"
    __table_args__ = (
        UniqueConstraint("rule_id", "step_order", name="uq_approval_rule_steps_rule_id_step_order"),
        CheckConstraint("step_order >= 1", name="ck_approval_rule_steps_order_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    rule_id: Mapped[int] = mapped_column(
        ForeignKey("approval_rules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_order: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    approver_role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False, index=True)

    rule: Mapped[ApprovalRule] = relationship(back_populates="steps")


class ApprovalStep(Base):
    """One step of the approval a document went through, kept as history after it is decided.

    A step names either the role that may decide it (from a rule) or, when no rule matched, the permission that
    qualifies someone (``required_permission``), which keeps single-step approval working with no rules set up.
    ``round`` counts submissions: a document sent back and resubmitted gets a new round and keeps the old one.
    """

    __tablename__ = "approval_steps"
    __table_args__ = (
        UniqueConstraint(
            "document_type", "document_id", "round", "step_order", name="uq_approval_steps_document_round_step"
        ),
        Index("ix_approval_steps_document", "document_type", "document_id"),
        CheckConstraint(
            "approver_role_id IS NOT NULL OR required_permission IS NOT NULL", name="ck_approval_steps_has_approver"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_type: Mapped[ApprovalDocumentType] = mapped_column(
        SAEnum(ApprovalDocumentType, name="approval_document_type"), nullable=False
    )
    document_id: Mapped[int] = mapped_column(Integer, nullable=False)
    round: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    step_order: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    approver_role_id: Mapped[int | None] = mapped_column(ForeignKey("roles.id"), index=True)
    required_permission: Mapped[str | None] = mapped_column(String(100))
    rule_id: Mapped[int | None] = mapped_column(ForeignKey("approval_rules.id", ondelete="SET NULL"), index=True)
    rule_name: Mapped[str | None] = mapped_column(String(150))
    # The document's amount in the base currency when the round opened; limits are checked against it.
    amount_base: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    status: Mapped[ApprovalStepStatus] = mapped_column(
        SAEnum(ApprovalStepStatus, name="approval_step_status"),
        nullable=False,
        default=ApprovalStepStatus.PENDING,
        index=True,
    )
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    # Set when a delegate decided for someone else: the person the decision was made on behalf of.
    on_behalf_of: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    comment: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ApprovalDelegation(Base):
    """While away, ``delegator`` lets ``delegate`` decide the approvals the delegator could decide."""

    __tablename__ = "approval_delegations"
    __table_args__ = (
        CheckConstraint("ends_on >= starts_on", name="ck_approval_delegations_dates_in_order"),
        CheckConstraint("delegator_id <> delegate_id", name="ck_approval_delegations_distinct_people"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    delegator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    delegate_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date] = mapped_column(Date, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    delegator: Mapped["User"] = relationship(foreign_keys=[delegator_id])
    delegate: Mapped["User"] = relationship(foreign_keys=[delegate_id])


class ApprovalLimit(Base):
    """The most a user may approve for one kind of document, in the base currency. No row means no limit."""

    __tablename__ = "approval_limits"
    __table_args__ = (
        UniqueConstraint("user_id", "document_type", name="uq_approval_limits_user_document_type"),
        CheckConstraint("max_amount >= 0", name="ck_approval_limits_amount_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    document_type: Mapped[ApprovalDocumentType] = mapped_column(
        SAEnum(ApprovalDocumentType, name="approval_document_type"), nullable=False
    )
    max_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    updated_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
