import pytest

from tests.support import login


async def test_me_requires_token(client):
    assert (await client.get("/me")).status_code == 401


async def test_first_request_creates_unonboarded_user(client):
    login(sub="auth0|u1")
    assert (await client.get("/me")).json() == {"handle": None, "display_name": None, "email": None, "onboarded": False}


async def test_onboarding_lowercases_handle(client):
    login()
    body = (await client.patch("/me", json={"handle": "@Fern_Fan", "display_name": "  Sam   Lee "})).json()
    assert body["handle"] == "fern_fan"
    assert body["display_name"] == "Sam Lee"
    assert body["onboarded"] is True


@pytest.mark.parametrize("handle", ["ab", "a" * 21, "has space", "dash-ed", "émile"])
async def test_invalid_handles_rejected(client, handle):
    login()
    assert (await client.patch("/me", json={"handle": handle})).status_code == 400


async def test_handle_unique_case_insensitively(client):
    login(sub="auth0|u1")
    assert (await client.patch("/me", json={"handle": "fern"})).status_code == 200
    login(sub="auth0|u2")
    assert (await client.patch("/me", json={"handle": "FERN"})).status_code == 409


async def test_handle_is_immutable(client):
    login()
    await client.patch("/me", json={"handle": "fern"})
    assert (await client.patch("/me", json={"handle": "Fern"})).status_code == 200  # same handle, different casing
    assert (await client.patch("/me", json={"handle": "basil"})).status_code == 400
    assert (await client.get("/me")).json()["handle"] == "fern"


async def test_display_name_editable(client):
    login()
    await client.patch("/me", json={"handle": "fern", "display_name": "Sam"})
    assert (await client.patch("/me", json={"display_name": "Samantha"})).json()["display_name"] == "Samantha"
    assert (await client.patch("/me", json={"display_name": "   "})).status_code == 400


async def test_email_synced_from_token(client):
    login(email="old@example.com")
    assert (await client.get("/me")).json()["email"] == "old@example.com"
    login(email="new@example.com")
    assert (await client.get("/me")).json()["email"] == "new@example.com"
