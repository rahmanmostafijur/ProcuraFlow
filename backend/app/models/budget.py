from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import BudgetChangeType, BudgetTransferStatus


class CostCentre(Base):
    """A department or cost centre that budgets are held against and that requests and orders are charged to."""

    __tablename__ = "cost_centres"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    manager_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    budgets: Mapped[list["Budget"]] = relationship(back_populates="cost_centre")


class Budget(Base):
    """The amount a cost centre may spend in one fiscal year, in the base currency.

    ``fiscal_year`` is the calendar year in which the fiscal year starts (see the fiscal year start month in the
    company settings). Spent, committed and remaining are computed by the metrics service, never stored here.
    """

    __tablename__ = "budgets"
    __table_args__ = (
        UniqueConstraint("cost_centre_id", "fiscal_year", name="uq_budgets_cost_centre_fiscal_year"),
        CheckConstraint("amount >= 0", name="ck_budgets_amount_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cost_centre_id: Mapped[int] = mapped_column(ForeignKey("cost_centres.id"), nullable=False, index=True)
    fiscal_year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    cost_centre: Mapped[CostCentre] = relationship(back_populates="budgets")


class BudgetTransfer(Base):
    """A request to move budget between two cost centres; it takes effect only when finance approves it."""

    __tablename__ = "budget_transfers"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_budget_transfers_amount_positive"),
        CheckConstraint("from_budget_id <> to_budget_id", name="ck_budget_transfers_distinct_budgets"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    from_budget_id: Mapped[int] = mapped_column(ForeignKey("budgets.id"), nullable=False, index=True)
    to_budget_id: Mapped[int] = mapped_column(ForeignKey("budgets.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[BudgetTransferStatus] = mapped_column(
        SAEnum(BudgetTransferStatus, name="budget_transfer_status"),
        nullable=False,
        default=BudgetTransferStatus.PENDING,
        index=True,
    )
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_comment: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    from_budget: Mapped[Budget] = relationship(foreign_keys=[from_budget_id])
    to_budget: Mapped[Budget] = relationship(foreign_keys=[to_budget_id])


class BudgetChange(Base):
    """One entry in a budget's history: every change to an amount is recorded here with who and why."""

    __tablename__ = "budget_changes"

    id: Mapped[int] = mapped_column(primary_key=True)
    budget_id: Mapped[int] = mapped_column(ForeignKey("budgets.id"), nullable=False, index=True)
    change_type: Mapped[BudgetChangeType] = mapped_column(
        SAEnum(BudgetChangeType, name="budget_change_type"), nullable=False
    )
    old_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    new_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500))
    transfer_id: Mapped[int | None] = mapped_column(ForeignKey("budget_transfers.id"), index=True)
    changed_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
