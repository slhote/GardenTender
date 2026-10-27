"""Purges gardens soft-deleted longer than GARDEN_RETENTION_DAYS. Run from cron: `uv run python -m app.jobs.purge`."""
import asyncio
import logging

from app.config import get_settings
from app.db import dispose_engine, get_sessionmaker
from app.services import gardens

log = logging.getLogger(__name__)


async def main() -> int:
    try:
        async with get_sessionmaker()() as session:
            purged = await gardens.purge_deleted(session, get_settings().garden_retention_days)
        log.info("Purged %d garden(s)", purged)
        return purged
    finally:
        await dispose_engine()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
