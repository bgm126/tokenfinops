import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, Boolean, Text, DateTime, JSON, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from tokenfinops.models.base import Base

# Dialect-independent JSON and UUID types
JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")

class UsageRecord(Base):
    __tablename__ = "usage_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        index=True, 
        default=uuid.uuid4
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        index=True, 
        default=func.now()
    )
    team_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    api_key_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Model parameters
    requested_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    routed_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    routing_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Token usage
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    original_input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_saved: Mapped[int] = mapped_column(Integer, default=0)

    # Costs
    estimated_cost: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    actual_cost: Mapped[float] = mapped_column(Numeric(10, 6), default=0.0)

    # Latency/Performance
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    time_to_first_token_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Cache metadata
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    cache_similarity: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Gateway metadata
    status: Mapped[str] = mapped_column(String(20), default="success", index=True)
    error_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    # Flexible metadata
    metadata_json: Mapped[dict | None] = mapped_column(JSON_TYPE, default=dict, nullable=True)
