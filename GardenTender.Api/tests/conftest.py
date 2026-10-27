import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import Base, get_sessionmaker
from app.main import app


@pytest.fixture
def client(tmp_path):
    """Real SQLAlchemy stack on a throwaway SQLite file, so tests need no Docker or Postgres."""
    from app import models  # noqa: F401

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")

    async def setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(setup())
    maker = async_sessionmaker(engine, expire_on_commit=False)

    app.dependency_overrides[get_sessionmaker] = lambda: maker
    yield TestClient(app)  # not used as a context manager, so the Postgres lifespan startup is skipped
    app.dependency_overrides.clear()
    asyncio.run(engine.dispose())
