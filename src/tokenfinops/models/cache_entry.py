import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, JSON, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from tokenfinops.models.base import Base

JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")

class DBCacheEntry(Base):
    __tablename__ = "cache_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    response_json: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    
    # Store embedding array as JSON for DB-agnostic serialization
    embedding: Mapped[list[float]] = mapped_column(JSON_TYPE, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    hit_count: Mapped[int] = mapped_column(Integer, default=0)
    ttl_seconds: Mapped[int] = mapped_column(Integer, default=3600)
