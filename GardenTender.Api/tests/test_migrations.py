from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from pathlib import Path
from sqlalchemy import create_engine

from app import models  # noqa: F401
from app.config import get_settings
from app.db import Base

API_ROOT = Path(__file__).resolve().parent.parent


def test_migrations_match_models(tmp_path, monkeypatch):
    db = tmp_path / "migrated.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db}")
    get_settings.cache_clear()
    try:
        command.upgrade(Config(str(API_ROOT / "alembic.ini")), "head")
    finally:
        get_settings.cache_clear()
    with create_engine(f"sqlite:///{db}").connect() as conn:
        assert compare_metadata(MigrationContext.configure(conn), Base.metadata) == []
