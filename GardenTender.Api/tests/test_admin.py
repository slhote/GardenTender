from tests.support import GLOBAL_ADMIN, create_garden, login, onboard


async def audit(client):
    login(GLOBAL_ADMIN, sub="auth0|root")
    return (await client.get("/admin/audit-log")).json()


async def test_admin_routes_require_global_admin(client):
    login(sub="auth0|ann")
    assert (await client.get("/admin/gardens")).status_code == 403
    assert (await client.get("/admin/audit-log")).status_code == 403


async def test_admin_lists_all_gardens_including_deleted(client):
    await onboard(client, "auth0|ann")
    a = await create_garden(client, "auth0|ann", "A")
    b = await create_garden(client, "auth0|ann", "B")
    login(sub="auth0|ann")
    await client.delete(f"/gardens/{b}")
    login(GLOBAL_ADMIN, sub="auth0|root")
    assert [g["id"] for g in (await client.get("/admin/gardens")).json()] == [a]
    assert [g["id"] for g in (await client.get("/admin/gardens", params={"include_deleted": True})).json()] == [a, b]


async def test_every_global_admin_request_is_audited(client):
    await onboard(client, "auth0|ann")
    gid = await create_garden(client, "auth0|ann")
    login(GLOBAL_ADMIN, sub="auth0|root")
    await client.get(f"/gardens/{gid}")  # reads too
    await client.patch(f"/gardens/{gid}", json={"name": "Renamed"})
    await client.patch(f"/gardens/{gid}/members/ann", json={"role": "contributor"})  # refused (last admin), still logged
    entries = await audit(client)
    # Newest first. The audit-log read itself is written after its response, so it isn't in its own result.
    assert [(e["method"], e["path"], e["status_code"], e["garden_id"]) for e in entries] == [
        ("PATCH", f"/gardens/{gid}/members/ann", 409, gid),
        ("PATCH", f"/gardens/{gid}", 200, gid),
        ("GET", f"/gardens/{gid}", 200, gid),
    ]
    assert entries[1]["body"] == {"name": "Renamed"}
    assert entries[1]["actor_sub"] == "auth0|root"


async def test_regular_users_are_not_audited(client):
    await onboard(client, "auth0|ann")
    await create_garden(client, "auth0|ann")
    assert await audit(client) == []


async def test_audit_redacts_secrets(client):
    login(GLOBAL_ADMIN, sub="auth0|root")
    await client.patch("/me", json={"display_name": "Root", "invite_token": "abc", "nested": {"password": "x"}})
    body = (await audit(client))[0]["body"]
    assert body == {"display_name": "Root", "invite_token": "[redacted]", "nested": {"password": "[redacted]"}}
