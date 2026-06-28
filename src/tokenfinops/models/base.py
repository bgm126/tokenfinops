from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from tokenfinops.config import settings

# Create async engine
# Note: For SQLite fallback during local dev if database is not postgres,
# we parse the DATABASE_URL and swap to standard sqlite+aiosqlite if required
database_url = settings.DATABASE_URL
if database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif database_url.startswith("sqlite://"):
    database_url = database_url.replace("sqlite://", "sqlite+aiosqlite://", 1)

engine = create_async_engine(
    database_url,
    pool_pre_ping=True,
    future=True,
)

# Async session factory
SessionLocal = async_sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

class Base(DeclarativeBase):
    pass

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for obtaining async database sessions in FastAPI."""
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
