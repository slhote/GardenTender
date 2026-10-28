import asyncio
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app import models  # noqa: F401
from app.config import get_settings
from app.db import Base
from tests.conftest import recreate_database

API_ROOT = Path(__file__).resolve().parent.parent


async def _drift(url) -> list:
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        diff = await conn.run_sync(lambda sync: compare_metadata(MigrationContext.configure(sync), Base.metadata))
    await engine.dispose()
    return diff


async def _tables(url) -> set[str]:
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        rows = await conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))
        names = {r[0] for r in rows}
    await engine.dispose()
    return names


def test_migrations_match_models_and_downgrade_cleanly(database_url, monkeypatch):
    url = database_url.set(database=f"{database_url.database}_migrations")
    asyncio.run(recreate_database(url))
    monkeypatch.setenv("DATABASE_URL", url.render_as_string(hide_password=False))
    get_settings.cache_clear()
    config = Config(str(API_ROOT / "alembic.ini"))
    try:
        command.upgrade(config, "head")
        assert asyncio.run(_drift(url)) == []
        command.downgrade(config, "base")
        assert asyncio.run(_tables(url)) == {"alembic_version"}
    finally:
        get_settings.cache_clear()
        asyncio.run(recreate_database(url, create=False))
