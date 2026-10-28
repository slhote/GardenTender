"""Guard for the explicit router list in app/main.py: every module in app/routers must be mounted.

main.py lists routers by hand on purpose (it is the allowlist of what the API serves, in a fixed order); this
test makes forgetting one fail loudly instead of surfacing as 404s.
"""
import importlib
import pkgutil
import re

from fastapi import APIRouter
from starlette.routing import Match

import app.routers
from app.main import app as fastapi_app


def _is_served(path: str, method: str) -> bool:
    """Whether the app routes `method path` anywhere (path parameters filled with a dummy value)."""
    scope = {"type": "http", "path": re.sub(r"\{[^}]+\}", "1", path), "method": method, "root_path": ""}
    return any(route.matches(scope)[0] == Match.FULL for route in fastapi_app.routes)


def test_every_router_module_is_mounted():
    missing = []
    for info in pkgutil.iter_modules(app.routers.__path__):
        module = importlib.import_module(f"app.routers.{info.name}")
        router = getattr(module, "router", None)
        assert isinstance(router, APIRouter), f"app/routers/{info.name}.py must define `router = APIRouter(...)`"
        if not all(_is_served(route.path, method) for route in router.routes for method in route.methods):
            missing.append(info.name)
    assert not missing, f"Routers not included in app/main.py: {missing}"
