"""Test helpers shared across test modules (fixtures live in conftest.py)."""
import asyncio

from app.auth import User, authenticate
from app.db import get_sessionmaker
from app.main import app
from app.routers.chat import get_provider

ALL = frozenset({"chat:use", "plants:read", "plants:write", "reminders:write", "calendar:write"})


class FakeProvider:
    """Replays scripted assistant turns and records what tools it was offered."""

    def __init__(self, turns):
        self.turns = list(turns)
        self.offered = []

    async def chat(self, system, messages, tools):
        self.offered.append([t.name for t in tools])
        return self.turns.pop(0)


def use(call_id, name, **input):
    return {"type": "tool_use", "id": call_id, "name": name, "input": input}


def text(t):
    return {"type": "text", "text": t}


def login(perms=ALL, sub="auth0|u1", email=None):
    app.dependency_overrides[authenticate] = lambda: User(sub=sub, permissions=perms, email=email)


def provider(turns):
    p = FakeProvider(turns)
    app.dependency_overrides[get_provider] = lambda: p
    return p


GLOBAL_ADMIN = frozenset({"system:admin"})


def onboard(client, sub, handle=None, perms=ALL):
    """Logs in as `sub` and completes onboarding with `handle` (defaults to the part of the sub after '|')."""
    login(perms, sub=sub)
    handle = handle or sub.split("|")[-1]
    assert client.patch("/me", json={"handle": handle, "display_name": handle.title()}).status_code == 200
    return handle


def create_garden(client, sub, name="Backyard"):
    login(sub=sub)
    r = client.post("/gardens", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def run_db(fn):
    """Runs `await fn(session)` against the test database and returns its result."""
    maker = app.dependency_overrides[get_sessionmaker]()

    async def run():
        async with maker() as session:
            return await fn(session)

    return asyncio.run(run())
