from collections.abc import AsyncIterator
from functools import lru_cache

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine() -> AsyncEngine:
    s = get_settings()
    # One pool per process. Keep workers * (pool_size + max_overflow) under Postgres max_connections.
    return create_async_engine(
        s.database_url,
        pool_size=s.db_pool_size,
        max_overflow=s.db_max_overflow,
        pool_pre_ping=True,
    )


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_session(maker: async_sessionmaker[AsyncSession] = Depends(get_sessionmaker)) -> AsyncIterator[AsyncSession]:
    async with maker() as session:
        yield session


async def dispose_engine() -> None:
    await get_engine().dispose()

