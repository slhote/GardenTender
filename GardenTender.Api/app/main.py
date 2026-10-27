from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import dispose_engine
from app.exception_handlers import register_exception_handlers
from app.routers import chat, me, plants


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Schema is managed by Alembic (`alembic upgrade head`), not created on startup.
    yield
    await dispose_engine()


app = FastAPI(title="GardenTender API", lifespan=lifespan)
register_exception_handlers(app)
for module in (chat, plants, me):
    app.include_router(module.router)
