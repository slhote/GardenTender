from sqlalchemy import select

from app.config import Settings, get_settings
from app.main import app
from app.models import QrCodeRow
from tests.support import GLOBAL_ADMIN, create_garden, garden_with_contributor, login, onboard, run_db

BASE = "https://gt.example.test"


def setup_garden(client):
    """ann's garden with bob as contributor and one plant. Leaves ann logged in."""
    app.dependency_overrides[get_settings] = lambda: Settings(public_base_url=BASE)
    gid = garden_with_contributor(client)
    login(sub="auth0|ann")
    pid = client.post(f"/gardens/{gid}/plants", json={"name": "Fern"}).json()["id"]
    return gid, pid


def codes_url(gid, qr_id=None):
    return f"/gardens/{gid}/qr-codes" + (f"/{qr_id}" if qr_id else "")


def token(code):
    return code["url"].rsplit("/", 1)[1]


def test_admin_creates_plant_and_garden_codes(client):
    gid, pid = setup_garden(client)
    plant_code = client.post(codes_url(gid), json={"target_type": "plant", "plant_id": pid, "label": "Fern tag"}).json()
    garden_code = client.post(codes_url(gid), json={"target_type": "garden"}).json()
    assert plant_code["url"].startswith(f"{BASE}/q/") and plant_code["label"] == "Fern tag"
    assert [c["id"] for c in client.get(codes_url(gid)).json()] == [plant_code["id"], garden_code["id"]]
    assert client.get(f"/qr/{token(plant_code)}").json() == {"target_type": "plant", "garden_id": gid, "plant_id": pid}
    assert client.get(f"/qr/{token(garden_code)}").json() == {"target_type": "garden", "garden_id": gid, "plant_id": None}


def test_contributors_scan_but_cannot_manage(client):
    gid, pid = setup_garden(client)
    code = client.post(codes_url(gid), json={"target_type": "plant", "plant_id": pid}).json()
    login(sub="auth0|bob")
    assert client.get(f"/qr/{token(code)}").status_code == 200
    assert client.post(codes_url(gid), json={"target_type": "garden"}).status_code == 403
    assert client.get(codes_url(gid)).status_code == 403
    assert client.patch(codes_url(gid, code["id"]), json={"label": "x"}).status_code == 403
    assert client.delete(codes_url(gid, code["id"])).status_code == 403


def test_non_members_get_generic_no_access(client):
    gid, _ = setup_garden(client)
    code = client.post(codes_url(gid), json={"target_type": "garden"}).json()
    onboard(client, "auth0|eve")
    for t in (token(code), "unknown"):
        r = client.get(f"/qr/{t}")
        assert (r.status_code, r.json()["detail"]) == (404, "QR code not found, or you don't have access to it.")


def test_global_admin_can_resolve_any_code(client):
    gid, _ = setup_garden(client)
    code = client.post(codes_url(gid), json={"target_type": "garden"}).json()
    login(GLOBAL_ADMIN, sub="auth0|root")
    assert client.get(f"/qr/{token(code)}").json()["garden_id"] == gid


def test_retarget_keeps_the_printed_url(client):
    gid, pid = setup_garden(client)
    code = client.post(codes_url(gid), json={"target_type": "garden"}).json()
    updated = client.patch(codes_url(gid, code["id"]), json={"target": {"target_type": "plant", "plant_id": pid}}).json()
    assert updated["url"] == code["url"]
    assert client.get(f"/qr/{token(code)}").json()["plant_id"] == pid


def test_delete_code_and_cascade_with_plant(client):
    gid, pid = setup_garden(client)
    plant_code = client.post(codes_url(gid), json={"target_type": "plant", "plant_id": pid}).json()
    garden_code = client.post(codes_url(gid), json={"target_type": "garden"}).json()
    assert client.delete(codes_url(gid, garden_code["id"])).status_code == 204
    client.delete(f"/gardens/{gid}/plants/{pid}")

    async def remaining(session):
        return list(await session.scalars(select(QrCodeRow.id)))

    assert run_db(remaining) == []
    assert client.get(f"/qr/{token(plant_code)}").status_code == 404


def test_deleted_garden_codes_stop_resolving(client):
    gid, _ = setup_garden(client)
    code = client.post(codes_url(gid), json={"target_type": "garden"}).json()
    client.delete(f"/gardens/{gid}")
    assert client.get(f"/qr/{token(code)}").status_code == 404


def test_validation(client):
    gid, pid = setup_garden(client)
    other = create_garden(client, "auth0|ann", "Other")
    login(sub="auth0|ann")
    assert client.post(codes_url(gid), json={"target_type": "plant"}).status_code == 422
    assert client.post(codes_url(gid), json={"target_type": "garden", "plant_id": pid}).status_code == 422
    assert client.post(codes_url(other), json={"target_type": "plant", "plant_id": pid}).status_code == 400
    assert client.post(codes_url(gid), json={"target_type": "shed"}).status_code == 422
    assert client.patch(codes_url(other, 999), json={"label": "x"}).status_code == 404
