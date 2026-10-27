"""Test helpers shared across test modules (fixtures live in conftest.py)."""
from app.auth import User, authenticate
from app.db import get_sessionmaker
from app.main import app
from app.routers.chat import get_provider

NO_PERMS = frozenset()  # regular users carry no Auth0 permissions; garden roles live in the database


class FakeProvider:
    """Replays scripted assistant turns and records what tools it was offered."""

    def __init__(self, turns):
        self.turns = list(turns)
        self.offered = []

    async def chat(self, system, messages, tools):
        self.offered.append([t.name for t in tools])
        return self.turns.pop(0)


def use(call_id, tool_name, **input):
    return {"type": "tool_use", "id": call_id, "name": tool_name, "input": input}


def text(t):
    return {"type": "text", "text": t}


def login(perms=NO_PERMS, sub="auth0|u1", email=None):
    app.dependency_overrides[authenticate] = lambda: User(sub=sub, permissions=perms, email=email)


def provider(turns):
    p = FakeProvider(turns)
    app.dependency_overrides[get_provider] = lambda: p
    return p


GLOBAL_ADMIN = frozenset({"system:admin"})


async def onboard(client, sub, handle=None, perms=NO_PERMS):
    """Logs in as `sub` and completes onboarding with `handle` (defaults to the part of the sub after '|')."""
    login(perms, sub=sub)
    handle = handle or sub.split("|")[-1]
    assert (await client.patch("/me", json={"handle": handle, "display_name": handle.title()})).status_code == 200
    return handle


async def create_garden(client, sub, name="Backyard"):
    login(sub=sub)
    r = await client.post("/gardens", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def run_db(fn):
    """Runs `await fn(session)` against the test database and returns its result."""
    maker = app.dependency_overrides[get_sessionmaker]()
    async with maker() as session:
        return await fn(session)


class CapturingEmailSender:
    def __init__(self):
        self.sent = []

    async def send(self, message):
        self.sent.append(message)


def capture_emails():
    """Routes outgoing email into a list for the rest of the test."""
    from app.dependencies import get_email_sender

    sender = CapturingEmailSender()
    app.dependency_overrides[get_email_sender] = lambda: sender
    return sender.sent


async def add_member(client, garden_id, handle, role="contributor"):
    """Adds a member directly as the global admin. Callers log in again afterwards."""
    login(GLOBAL_ADMIN, sub="auth0|root")
    r = await client.post(f"/gardens/{garden_id}/members", json={"handle": handle, "role": role})
    assert r.status_code == 201, r.text


async def garden_with_contributor(client):
    """ann (admin) owns a garden and bob is a contributor. Returns the garden id."""
    await onboard(client, "auth0|ann")
    gid = await create_garden(client, "auth0|ann")
    await onboard(client, "auth0|bob")
    await add_member(client, gid, "bob")
    return gid
