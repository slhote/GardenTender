from sqlalchemy import select

from app.models import GardenEventRow
from tests.support import GLOBAL_ADMIN, add_member, garden_with_contributor, login, onboard, run_db


def url(gid, rid=None, action=None):
    return f"/gardens/{gid}/requests" + (f"/{rid}" if rid else "") + (f"/{action}" if action else "")


def plant_request(client, gid, name="Basil", note="for pesto"):
    login(sub="auth0|bob")
    r = client.post(url(gid), json={"type": "create_plant", "payload": {"name": name}, "note": note})
    assert r.status_code == 201, r.text
    return r.json()


def plant_names(client, gid):
    return [p["name"] for p in client.get(f"/gardens/{gid}/plants").json()]


async def _event_types(session, gid):
    query = select(GardenEventRow.type).where(GardenEventRow.garden_id == gid).order_by(GardenEventRow.id)
    return list(await session.scalars(query))


def test_contributor_request_waits_for_approval(client):
    gid = garden_with_contributor(client)
    req = plant_request(client, gid)
    assert req["status"] == "pending" and req["note"] == "for pesto" and req["requested_by"] == "bob"
    assert plant_names(client, gid) == []


def test_admin_approves_with_reason(client):
    gid = garden_with_contributor(client)
    req = plant_request(client, gid)
    login(sub="auth0|ann")
    approved = client.post(url(gid, req["id"], "approve"), json={"reason": "good idea"}).json()
    assert (approved["status"], approved["decided_by"], approved["decision_reason"]) == ("approved", "ann", "good idea")
    assert plant_names(client, gid) == ["Basil"]
    assert approved["result"]["plant_id"] == client.get(f"/gardens/{gid}/plants").json()[0]["id"]
    assert run_db(lambda s: _event_types(s, gid))[-3:] == ["request.created", "plant.created", "request.approved"]


def test_admin_edits_then_approves(client):
    gid = garden_with_contributor(client)
    req = plant_request(client, gid, name="basel")
    login(sub="auth0|ann")
    edited = client.patch(url(gid, req["id"]), json={"payload": {"name": "Basil", "water_every_days": 2}}).json()
    assert edited["payload"]["name"] == "Basil"
    client.post(url(gid, req["id"], "approve"), json={})
    [plant] = client.get(f"/gardens/{gid}/plants").json()
    assert (plant["name"], plant["water_every_days"]) == ("Basil", 2)


def test_admin_rejects(client):
    gid = garden_with_contributor(client)
    req = plant_request(client, gid)
    login(sub="auth0|ann")
    rejected = client.post(url(gid, req["id"], "reject"), json={"reason": "no room"}).json()
    assert (rejected["status"], rejected["decision_reason"]) == ("rejected", "no room")
    assert plant_names(client, gid) == []


def test_decided_requests_are_final(client):
    gid = garden_with_contributor(client)
    req = plant_request(client, gid)
    login(sub="auth0|ann")
    client.post(url(gid, req["id"], "reject"), json={})
    assert client.post(url(gid, req["id"], "approve"), json={}).status_code == 409
    assert client.patch(url(gid, req["id"]), json={"note": "x"}).status_code == 409


def test_requester_cancels_own_pending_request(client):
    gid = garden_with_contributor(client)
    req = plant_request(client, gid)
    login(sub="auth0|ann")
    assert client.post(url(gid, req["id"], "cancel")).status_code == 403  # only the requester
    login(sub="auth0|bob")
    assert client.post(url(gid, req["id"], "cancel")).json()["status"] == "cancelled"


def test_contributor_cannot_decide_or_edit(client):
    gid = garden_with_contributor(client)
    req = plant_request(client, gid)
    assert client.post(url(gid, req["id"], "approve"), json={}).status_code == 403
    assert client.post(url(gid, req["id"], "reject"), json={}).status_code == 403
    assert client.patch(url(gid, req["id"]), json={"note": "x"}).status_code == 403


def test_contributors_only_see_their_own_requests(client):
    gid = garden_with_contributor(client)
    onboard(client, "auth0|cat")
    add_member(client, gid, "cat")
    bobs = plant_request(client, gid)
    login(sub="auth0|cat")
    assert client.get(url(gid)).json() == []
    assert client.get(url(gid, bobs["id"])).status_code == 404
    login(sub="auth0|ann")
    assert [r["id"] for r in client.get(url(gid), params={"status": "pending"}).json()] == [bobs["id"]]


def test_admin_requests_are_auto_approved(client):
    gid = garden_with_contributor(client)
    login(sub="auth0|ann")
    req = client.post(url(gid), json={"type": "create_plant", "payload": {"name": "Mint"}}).json()
    assert (req["status"], req["decided_by"]) == ("approved", "ann")
    assert plant_names(client, gid) == ["Mint"]


def test_invalid_requests_rejected_up_front(client):
    gid = garden_with_contributor(client)
    login(sub="auth0|bob")
    assert client.post(url(gid), json={"type": "teleport", "payload": {}}).status_code == 400
    assert client.post(url(gid), json={"type": "create_plant", "payload": {"name": " "}}).status_code == 400
    assert client.post(url(gid), json={"type": "create_plant", "payload": {}}).status_code == 400
    long_note = {"type": "create_plant", "payload": {"name": "Basil"}, "note": "x" * 501}
    assert client.post(url(gid), json=long_note).status_code == 400


def test_global_admin_can_decide(client):
    gid = garden_with_contributor(client)
    req = plant_request(client, gid)
    login(GLOBAL_ADMIN, sub="auth0|root")
    assert client.post(url(gid, req["id"], "approve"), json={}).json()["status"] == "approved"
