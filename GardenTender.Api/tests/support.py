"""Test helpers shared across test modules (fixtures live in conftest.py)."""
from app.auth import User, get_current_user
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
    app.dependency_overrides[get_current_user] = lambda: User(sub=sub, permissions=perms, email=email)


def provider(turns):
    p = FakeProvider(turns)
    app.dependency_overrides[get_provider] = lambda: p
    return p
