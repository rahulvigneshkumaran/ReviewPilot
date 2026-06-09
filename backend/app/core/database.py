from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# SQLite does not support connection pool sizing; only pass those args for Postgres
_is_sqlite = settings.SQLALCHEMY_DATABASE_URI.startswith("sqlite")
_engine_kwargs = {
    "echo": False,
    "pool_pre_ping": not _is_sqlite,  # pool_pre_ping not meaningful for SQLite
}
if not _is_sqlite:
    _engine_kwargs["pool_size"] = 20
    _engine_kwargs["max_overflow"] = 10

# Create database engine
engine = create_async_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    **_engine_kwargs,
)

# Async session factory
async_session_factory = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency generator for database sessions in FastAPI routes."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
