from tests.support import ALL, GLOBAL_ADMIN, create_garden, login, onboard


def audit(client):
    login(GLOBAL_ADMIN, sub="auth0|root")
    return client.get("/admin/audit-log").json()


def test_admin_routes_require_global_admin(client):
    login(ALL, sub="auth0|ann")
    assert client.get("/admin/gardens").status_code == 403
    assert client.get("/admin/audit-log").status_code == 403


def test_admin_lists_all_gardens_including_deleted(client):
    onboard(client, "auth0|ann")
    a = create_garden(client, "auth0|ann", "A")
    b = create_garden(client, "auth0|ann", "B")
    login(sub="auth0|ann")
    client.delete(f"/gardens/{b}")
    login(GLOBAL_ADMIN, sub="auth0|root")
    assert [g["id"] for g in client.get("/admin/gardens").json()] == [a]
    assert [g["id"] for g in client.get("/admin/gardens", params={"include_deleted": True}).json()] == [a, b]


def test_every_global_admin_request_is_audited(client):
    onboard(client, "auth0|ann")
    gid = create_garden(client, "auth0|ann")
    login(GLOBAL_ADMIN, sub="auth0|root")
    client.get(f"/gardens/{gid}")  # reads too
    client.patch(f"/gardens/{gid}", json={"name": "Renamed"})
    client.patch(f"/gardens/{gid}/members/ann", json={"role": "contributor"})  # refused (last admin), still logged
    entries = audit(client)
    # Newest first. The audit-log read itself is written after its response, so it isn't in its own result.
    assert [(e["method"], e["path"], e["status_code"], e["garden_id"]) for e in entries] == [
        ("PATCH", f"/gardens/{gid}/members/ann", 409, gid),
        ("PATCH", f"/gardens/{gid}", 200, gid),
        ("GET", f"/gardens/{gid}", 200, gid),
    ]
    assert entries[1]["body"] == {"name": "Renamed"}
    assert entries[1]["actor_sub"] == "auth0|root"


def test_regular_users_are_not_audited(client):
    onboard(client, "auth0|ann")
    create_garden(client, "auth0|ann")
    assert audit(client) == []


def test_audit_redacts_secrets(client):
    login(GLOBAL_ADMIN, sub="auth0|root")
    client.patch("/me", json={"display_name": "Root", "invite_token": "abc", "nested": {"password": "x"}})
    body = audit(client)[0]["body"]
    assert body == {"display_name": "Root", "invite_token": "[redacted]", "nested": {"password": "[redacted]"}}
