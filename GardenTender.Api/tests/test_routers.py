"""Guard for the explicit router list in app/main.py: every module in app/routers must be mounted.

main.py lists routers by hand on purpose (it is the allowlist of what the API serves, in a fixed order); this
test makes forgetting one fail loudly instead of surfacing as 404s. A module that is deliberately not in the
list (debug-only, or merged but not ready) declares `NOT_MOUNTED = "<reason>"` and is skipped.
"""
import importlib
import pkgutil
import re

from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.routing import Match

import app.routers
from app.auth import User, authenticate
from app.config import Settings
from app.db import get_sessionmaker
from app.main import app as fastapi_app
from app.main import create_app


def _is_served(application: FastAPI, path: str, method: str) -> bool:
    """Whether the app routes `method path` anywhere (path parameters filled with a dummy value)."""
    scope = {"type": "http", "path": re.sub(r"\{[^}]+\}", "1", path), "method": method, "root_path": ""}
    return any(route.matches(scope)[0] == Match.FULL for route in application.routes)


def _router_modules():
    for info in pkgutil.iter_modules(app.routers.__path__):
        yield info.name, importlib.import_module(f"app.routers.{info.name}")


def test_every_router_module_is_mounted():
    missing = []
    for name, module in _router_modules():
        router = getattr(module, "router", None)
        assert isinstance(router, APIRouter), f"app/routers/{name}.py must define `router = APIRouter(...)`"
        if getattr(module, "NOT_MOUNTED", None):
            continue  # deliberately left out; the reason lives in the module
        if not all(_is_served(fastapi_app, route.path, method) for route in router.routes for method in route.methods):
            missing.append(name)
    assert not missing, f"Routers not included in app/main.py: {missing}"


def test_not_mounted_reasons_are_explained():
    for name, module in _router_modules():
        reason = getattr(module, "NOT_MOUNTED", None)
        assert reason is None or (isinstance(reason, str) and reason.strip()), f"{name}.NOT_MOUNTED needs a reason"


async def _get(database_url, debug_endpoints: bool, *, logged_in: bool = True):
    """GET /debug/whoami on a fresh app built with the flag, wired to the test database like the main app."""
    application = create_app(Settings(debug_endpoints=debug_endpoints))
    engine = create_async_engine(database_url)
    application.dependency_overrides[get_sessionmaker] = lambda: async_sessionmaker(engine, expire_on_commit=False)
    if logged_in:
        application.dependency_overrides[authenticate] = lambda: User(
            sub="auth0|dev", permissions=frozenset({"system:admin"}), email="dev@example.com"
        )
    try:
        async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as http:
            return await http.get("/debug/whoami")
    finally:
        await engine.dispose()


# `client` is requested only so each test starts from empty tables (the audit log row lands in the test DB).
async def test_debug_endpoints_are_absent_when_off(client, database_url):
    assert (await _get(database_url, debug_endpoints=False)).status_code == 404


async def test_debug_endpoints_work_when_on(client, database_url):
    response = await _get(database_url, debug_endpoints=True)
    assert response.json() == {
        "sub": "auth0|dev",
        "email": "dev@example.com",
        "permissions": ["system:admin"],
        "is_global_admin": True,
    }


async def test_debug_endpoints_still_require_login(client, database_url):
    assert (await _get(database_url, debug_endpoints=True, logged_in=False)).status_code == 401
