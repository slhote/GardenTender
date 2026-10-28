from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.audit import AuditMiddleware
from app.config import Settings, get_settings
from app.db import dispose_engine, get_sessionmaker
from app.exception_handlers import register_exception_handlers
from app.routers import admin, chat, debug, gardens, invites, links, me, plants, qr_codes, requests, users


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Schema is managed by Alembic (`alembic upgrade head`), not created on startup.
    yield
    await dispose_engine()


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="GardenTender API", lifespan=lifespan)
    register_exception_handlers(app)
    # Resolved per request so it honors dependency_overrides (tests point it at their own database).
    app.add_middleware(AuditMiddleware, get_sessionmaker=lambda: app.dependency_overrides.get(get_sessionmaker, get_sessionmaker)())
    # Explicit on purpose: this is the allowlist of what the API serves, in match order. tests/test_routers.py fails
    # if a module in app/routers is missing here, unless the module declares NOT_MOUNTED with a reason.
    for module in (chat, plants, me, users, gardens, requests, invites, qr_codes, links, admin):
        app.include_router(module.router)
    # Debug-only routes exist only when switched on at startup: in production they are never mounted at all.
    if settings.debug_endpoints:
        app.include_router(debug.router)
    return app


app = create_app(get_settings())
