"""Tests run against Postgres, the production database, in a dedicated `<dev db>_test` database.

Start it with `docker compose up -d db`. The test database is created if missing and its schema rebuilt once per
run; every test then starts from empty tables. Set TEST_DATABASE_URL to use a different server or database (its
name must end in `_test`, so a dev database can never be wiped by accident).
"""
import asyncio
import os

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import URL, make_url, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db import Base, get_sessionmaker
from app.main import app


def _test_database_url() -> URL:
    raw = os.environ.get("TEST_DATABASE_URL")
    if raw:
        url = make_url(raw)
    else:
        if not get_settings().database_url:
            raise pytest.UsageError("Set DATABASE_URL in .env (or TEST_DATABASE_URL) to a Postgres server for the tests.")
        dev = make_url(get_settings().database_url)
        # Docker publishes Postgres on IPv4 only; "localhost" tries IPv6 first on Windows and stalls ~20s per connection.
        url = dev.set(host="127.0.0.1" if dev.host == "localhost" else dev.host, database=f"{dev.database}_test")
    if not url.drivername.startswith("postgresql"):
        raise pytest.UsageError(f"Tests need a Postgres URL, got {url.drivername!r}.")
    if not url.database or not url.database.endswith("_test"):
        raise pytest.UsageError(f"Refusing to wipe database {url.database!r}: test database names must end in '_test'.")
    return url


async def recreate_database(url: URL, *, create: bool = True) -> None:
    """Drops `url`'s database and, unless `create=False`, creates it empty (the migration test needs a bare one)."""
    admin = create_async_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        await conn.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
        if create:
            await conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    await admin.dispose()


async def _prepare(url: URL) -> None:
    admin = create_async_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        exists = await conn.scalar(text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": url.database})
        if not exists:
            await conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    await admin.dispose()

    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


@pytest.fixture(scope="session")
def database_url() -> URL:
    """The test database, with a fresh schema built from the models once per run."""
    from app import models  # noqa: F401  (registers tables on Base.metadata)

    url = _test_database_url()
    asyncio.run(_prepare(url))  # its own short-lived loop; nothing from it is reused by the tests
    return url


@pytest.fixture
async def client(database_url):
    """The real app and SQLAlchemy stack on the test's own event loop, starting from empty tables."""
    engine = create_async_engine(database_url)
    tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    maker = async_sessionmaker(engine, expire_on_commit=False)

    app.dependency_overrides[get_sessionmaker] = lambda: maker
    # ASGITransport skips the lifespan, so the app's own engine is never created.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http
    app.dependency_overrides.clear()
    await engine.dispose()
