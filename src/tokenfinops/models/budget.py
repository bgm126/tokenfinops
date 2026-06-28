import uuid
from datetime import datetime
from sqlalchemy import String, Numeric, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from tokenfinops.models.base import Base

class Budget(Base):
    __tablename__ = "budgets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    team_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    period: Mapped[str] = mapped_column(String(20), default="monthly")  # daily, weekly, monthly
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    soft_limit_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=70.00)
    hard_limit_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=95.00)
    downgrade_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    alert_webhook: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=func.now(), 
        onupdate=func.now()
    )

    usages: Mapped[list["BudgetUsage"]] = relationship(
        "BudgetUsage", 
        back_populates="budget", 
        cascade="all, delete-orphan"
    )

class BudgetUsage(Base):
    __tablename__ = "budget_usages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    budget_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("budgets.id", ondelete="CASCADE"), 
        index=True, 
        nullable=False
    )
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    spent: Mapped[float] = mapped_column(Numeric(10, 6), default=0.0)
    request_count: Mapped[int] = mapped_column(Integer, default=0)

    budget: Mapped[Budget] = relationship("Budget", back_populates="usages")
