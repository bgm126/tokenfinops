import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, JSON, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from tokenfinops.models.base import Base

JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")

class DBRecommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    team_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False)  # model_routing, caching, prompt_optimization, budget
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_savings: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default="medium")  # low, medium, high, critical
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)  # active, dismissed, implemented
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    metadata_json: Mapped[dict | None] = mapped_column(JSON_TYPE, default=dict, nullable=True)
