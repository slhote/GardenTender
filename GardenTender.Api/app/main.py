from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.audit import AuditMiddleware
from app.db import dispose_engine, get_sessionmaker
from app.exception_handlers import register_exception_handlers
from app.routers import admin, chat, gardens, invites, links, me, plants, requests, users


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Schema is managed by Alembic (`alembic upgrade head`), not created on startup.
    yield
    await dispose_engine()


app = FastAPI(title="GardenTender API", lifespan=lifespan)
register_exception_handlers(app)
# Resolved per request so it honors dependency_overrides (tests point it at their own database).
app.add_middleware(AuditMiddleware, get_sessionmaker=lambda: app.dependency_overrides.get(get_sessionmaker, get_sessionmaker)())
for module in (chat, plants, me, users, gardens, requests, invites, links, admin):
    app.include_router(module.router)
