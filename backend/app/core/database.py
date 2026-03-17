from collections.abc import AsyncGenerator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# Async engine (for FastAPI endpoints)
async_engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Sync engine (for Celery workers)
sync_engine = create_engine(
    settings.database_url_sync,
    echo=settings.debug,
    pool_pre_ping=True,
)

SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    expire_on_commit=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session


@contextmanager
def get_sync_session() -> Session:
    session = SyncSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
