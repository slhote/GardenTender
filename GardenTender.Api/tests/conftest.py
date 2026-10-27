import os

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import Base, get_sessionmaker
from app.main import app


def _sqlite_foreign_keys(dbapi_connection, _):
    # SQLite ignores foreign keys unless asked; Postgres always enforces them, so tests should too.
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture
async def client(tmp_path):
    """The real app and SQLAlchemy stack, all on the test's own event loop.

    Uses a throwaway SQLite file by default, so tests need no Docker or Postgres. Set TEST_DATABASE_URL to a
    scratch Postgres database (postgresql+asyncpg://...) to run the same suite there; it is wiped per test.
    """
    from app import models  # noqa: F401

    engine = create_async_engine(os.environ.get("TEST_DATABASE_URL") or f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    if engine.dialect.name == "sqlite":
        event.listen(engine.sync_engine, "connect", _sqlite_foreign_keys)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    app.dependency_overrides[get_sessionmaker] = lambda: maker
    # ASGITransport skips the lifespan, so the app's own engine is never created.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http
    app.dependency_overrides.clear()
    await engine.dispose()
