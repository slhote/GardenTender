import re
from datetime import UTC, datetime, timedelta

from sqlalchemy import update

from app.config import Settings, get_settings
from app.main import app
from app.models import InviteRow, UserRow
from tests.support import GLOBAL_ADMIN, capture_emails, create_garden, garden_with_contributor, login, onboard, run_db

BASE = "https://gt.example.test"


def use_public_url():
    app.dependency_overrides[get_settings] = lambda: Settings(public_base_url=BASE)


def token_from(message):
    return re.search(rf"{re.escape(BASE)}/i/(\S+)", message.body).group(1)


async def _exec(session, stmt):
    await session.execute(stmt)
    await session.commit()


async def set_email(sub, email):
    await run_db(lambda s: _exec(s, update(UserRow).where(UserRow.sub == sub).values(email=email)))


async def members(client, gid):
    return {m["handle"]: m for m in (await client.get(f"/gardens/{gid}/members")).json()}


async def test_admin_invites_by_email_and_link_joins(client):
    use_public_url()
    sent = capture_emails()
    await onboard(client, "auth0|ann")
    gid = await create_garden(client, "auth0|ann")
    login(sub="auth0|ann")
    out = (await client.post(f"/gardens/{gid}/invites", json={"email": "New@Example.com"})).json()
    assert (out["via"], out["email"], out["role"], out["invited_by"]) == ("email", "new@example.com", "contributor", "ann")
    [message] = sent
    assert message.to == "new@example.com" and "@ann invited you" in message.body

    await onboard(client, "auth0|zed")  # signed up with some other email: the link still works
    assert (await client.post("/invites/accept", json={"token": token_from(message)})).json() == {"garden_id": gid}
    login(sub="auth0|ann")
    zed = (await members(client, gid))["zed"]
    assert (zed["role"], zed["invited_by"], zed["approved_by"]) == ("contributor", "ann", None)


async def test_link_is_single_use(client):
    use_public_url()
    sent = capture_emails()
    await onboard(client, "auth0|ann")
    gid = await create_garden(client, "auth0|ann")
    login(sub="auth0|ann")
    await client.post(f"/gardens/{gid}/invites", json={"email": "a@example.com"})
    token = token_from(sent[0])
    await onboard(client, "auth0|zed")
    assert (await client.post("/invites/accept", json={"token": token})).status_code == 200
    await onboard(client, "auth0|yan")
    assert (await client.post("/invites/accept", json={"token": token})).status_code == 404


async def test_expired_revoked_and_bogus_tokens_fail_alike(client):
    use_public_url()
    sent = capture_emails()
    await onboard(client, "auth0|ann")
    gid = await create_garden(client, "auth0|ann")
    login(sub="auth0|ann")
    expired = (await client.post(f"/gardens/{gid}/invites", json={"email": "a@example.com"})).json()
    revoked = (await client.post(f"/gardens/{gid}/invites", json={"email": "b@example.com"})).json()
    past = datetime.now(UTC) - timedelta(minutes=1)
    await run_db(lambda s: _exec(s, update(InviteRow).where(InviteRow.id == expired["id"]).values(expires_at=past)))
    assert (await client.delete(f"/gardens/{gid}/invites/{revoked['id']}")).status_code == 204
    assert (await client.get(f"/gardens/{gid}/invites")).json() == []

    await onboard(client, "auth0|zed")
    for token in (token_from(sent[0]), token_from(sent[1]), "not-a-token"):
        r = await client.post("/invites/accept", json={"token": token})
        assert (r.status_code, r.json()["detail"]) == (404, "This invite is no longer valid.")


async def test_tokens_are_stored_hashed(client):
    use_public_url()
    sent = capture_emails()
    await onboard(client, "auth0|ann")
    gid = await create_garden(client, "auth0|ann")
    login(sub="auth0|ann")
    await client.post(f"/gardens/{gid}/invites", json={"email": "a@example.com"})

    async def stored(session):
        return (await session.get(InviteRow, 1)).token_hash

    assert token_from(sent[0]) not in await run_db(stored)


async def test_invite_existing_user_by_handle_shows_in_app(client):
    sent = capture_emails()
    await onboard(client, "auth0|ann")
    gid = await create_garden(client, "auth0|ann")
    await onboard(client, "auth0|bob")
    await set_email("auth0|bob", "bob@example.com")
    login(sub="auth0|ann")
    out = (await client.post(f"/gardens/{gid}/invites", json={"handle": "@BOB", "role": "admin"})).json()
    assert (out["handle"], out["email"], out["role"]) == ("bob", None, "admin")  # bob's email is never shown
    assert sent[0].to == "bob@example.com"

    login(sub="auth0|bob")
    [mine] = (await client.get("/me/invites")).json()
    assert (mine["garden_name"], mine["role"], mine["invited_by"]) == ("Backyard", "admin", "ann")
    assert (await client.post(f"/me/invites/{mine['id']}/accept")).json() == {"garden_id": gid}
    assert (await client.get("/me/invites")).json() == []
    assert (await client.get(f"/gardens/{gid}")).json()["my_role"] == "admin"


async def test_email_invite_to_existing_account_appears_in_app_without_revealing_it(client):
    capture_emails()
    await onboard(client, "auth0|ann")
    gid = await create_garden(client, "auth0|ann")
    await onboard(client, "auth0|bob")
    await set_email("auth0|bob", "bob@example.com")
    login(sub="auth0|ann")
    out = (await client.post(f"/gardens/{gid}/invites", json={"email": "bob@example.com"})).json()
    assert out["handle"] is None
    login(sub="auth0|bob")
    assert len((await client.get("/me/invites")).json()) == 1


async def test_decline_and_others_cannot_touch_my_invite(client):
    capture_emails()
    await onboard(client, "auth0|ann")
    gid = await create_garden(client, "auth0|ann")
    await onboard(client, "auth0|bob")
    login(sub="auth0|ann")
    invite_id = (await client.post(f"/gardens/{gid}/invites", json={"handle": "bob"})).json()["id"]
    await onboard(client, "auth0|eve")
    assert (await client.post(f"/me/invites/{invite_id}/accept")).status_code == 404
    login(sub="auth0|bob")
    assert (await client.post(f"/me/invites/{invite_id}/decline")).status_code == 204
    assert (await client.post(f"/me/invites/{invite_id}/accept")).status_code == 404


async def test_invite_validation(client):
    capture_emails()
    await onboard(client, "auth0|ann")
    gid = await create_garden(client, "auth0|ann")
    login(sub="auth0|ann")
    assert (await client.post(f"/gardens/{gid}/invites", json={})).status_code == 422
    assert (await client.post(f"/gardens/{gid}/invites", json={"email": "nope"})).status_code == 422
    assert (await client.post(f"/gardens/{gid}/invites", json={"handle": "a", "email": "a@b.co"})).status_code == 422
    assert (await client.post(f"/gardens/{gid}/invites", json={"handle": "ghost"})).status_code == 404
    assert (await client.post(f"/gardens/{gid}/invites", json={"handle": "ann"})).status_code == 409


async def test_accepting_requires_onboarding_and_not_already_member(client):
    use_public_url()
    sent = capture_emails()
    await onboard(client, "auth0|ann")
    gid = await create_garden(client, "auth0|ann")
    login(sub="auth0|ann")
    await client.post(f"/gardens/{gid}/invites", json={"email": "a@example.com"})
    token = token_from(sent[0])
    login(sub="auth0|new")
    assert (await client.post("/invites/accept", json={"token": token})).status_code == 403
    login(sub="auth0|ann")
    assert (await client.post("/invites/accept", json={"token": token})).status_code == 409


async def test_contributor_invite_goes_through_approval(client):
    use_public_url()
    sent = capture_emails()
    gid = await garden_with_contributor(client)
    login(sub="auth0|bob")
    assert (await client.post(f"/gardens/{gid}/invites", json={"email": "c@example.com"})).status_code == 403
    req = (await client.post(
        f"/gardens/{gid}/requests",
        json={"type": "invite_user", "payload": {"email": "c@example.com"}, "note": "my sister"},
    )).json()
    assert req["status"] == "pending" and req["payload"]["role"] == "contributor"
    assert sent == []  # nothing sent until approved

    login(sub="auth0|ann")
    await client.patch(f"/gardens/{gid}/requests/{req['id']}", json={"payload": {"email": "c@example.com", "role": "admin"}})
    approved = (await client.post(f"/gardens/{gid}/requests/{req['id']}/approve", json={})).json()
    assert approved["status"] == "approved" and "invite_id" in approved["result"]
    [message] = sent
    assert "@bob (approved by @ann) invited you" in message.body and "as admin" in message.body
    [pending] = (await client.get(f"/gardens/{gid}/invites")).json()
    assert (pending["invited_by"], pending["approved_by"]) == ("bob", "ann")

    await onboard(client, "auth0|cat")
    await client.post("/invites/accept", json={"token": token_from(message)})
    login(sub="auth0|ann")
    cat = (await members(client, gid))["cat"]
    assert (cat["role"], cat["invited_by"], cat["approved_by"]) == ("admin", "bob", "ann")


async def test_qr_invite_is_admin_only_short_lived_single_use(client):
    use_public_url()
    gid = await garden_with_contributor(client)
    login(sub="auth0|bob")
    assert (await client.post(f"/gardens/{gid}/invites/qr", json={})).status_code == 403
    login(sub="auth0|ann")
    qr = (await client.post(f"/gardens/{gid}/invites/qr", json={})).json()
    assert qr["url"].startswith(f"{BASE}/i/")
    expires = datetime.fromisoformat(qr["expires_at"])
    expires = expires if expires.tzinfo else expires.replace(tzinfo=UTC)
    assert expires - datetime.now(UTC) <= timedelta(minutes=15)
    token = qr["url"].rsplit("/", 1)[1]
    await onboard(client, "auth0|cat")
    assert (await client.post("/invites/accept", json={"token": token})).status_code == 200
    await onboard(client, "auth0|dan")
    assert (await client.post("/invites/accept", json={"token": token})).status_code == 404


async def test_deleted_garden_invites_stop_working(client):
    use_public_url()
    sent = capture_emails()
    await onboard(client, "auth0|ann")
    gid = await create_garden(client, "auth0|ann")
    login(sub="auth0|ann")
    await client.post(f"/gardens/{gid}/invites", json={"email": "a@example.com"})
    await client.delete(f"/gardens/{gid}")
    await onboard(client, "auth0|zed")
    assert (await client.post("/invites/accept", json={"token": token_from(sent[0])})).status_code == 404


async def test_accept_token_is_redacted_in_admin_audit(client):
    login(GLOBAL_ADMIN, sub="auth0|root")
    await client.post("/invites/accept", json={"token": "secret-value"})
    [entry] = (await client.get("/admin/audit-log")).json()
    assert entry["body"] == {"token": "[redacted]"}


async def test_public_link_pages_and_assetlinks(client):
    assert "invited" in (await client.get("/i/anything")).text
    assert (await client.get("/q/anything")).status_code == 200
    assert (await client.get("/.well-known/assetlinks.json")).status_code == 404
    app.dependency_overrides[get_settings] = lambda: Settings(android_cert_sha256=["AB:CD"])
    [statement] = (await client.get("/.well-known/assetlinks.json")).json()
    assert statement["target"] == {
        "namespace": "android_app", "package_name": "com.gardentender", "sha256_cert_fingerprints": ["AB:CD"]
    }
