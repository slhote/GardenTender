from sqlalchemy import select

from app.models import GardenEventRow
from tests.support import GLOBAL_ADMIN, add_member, garden_with_contributor, login, onboard, run_db


def url(gid, rid=None, action=None):
    return f"/gardens/{gid}/requests" + (f"/{rid}" if rid else "") + (f"/{action}" if action else "")


async def plant_request(client, gid, name="Basil", note="for pesto"):
    login(sub="auth0|bob")
    r = await client.post(url(gid), json={"type": "create_plant", "payload": {"name": name}, "note": note})
    assert r.status_code == 201, r.text
    return r.json()


async def plant_names(client, gid):
    return [p["name"] for p in (await client.get(f"/gardens/{gid}/plants")).json()]


async def _event_types(session, gid):
    query = select(GardenEventRow.type).where(GardenEventRow.garden_id == gid).order_by(GardenEventRow.id)
    return list(await session.scalars(query))


async def test_contributor_request_waits_for_approval(client):
    gid = await garden_with_contributor(client)
    req = await plant_request(client, gid)
    assert req["status"] == "pending" and req["note"] == "for pesto" and req["requested_by"] == "bob"
    assert await plant_names(client, gid) == []


async def test_admin_approves_with_reason(client):
    gid = await garden_with_contributor(client)
    req = await plant_request(client, gid)
    login(sub="auth0|ann")
    approved = (await client.post(url(gid, req["id"], "approve"), json={"reason": "good idea"})).json()
    assert (approved["status"], approved["decided_by"], approved["decision_reason"]) == ("approved", "ann", "good idea")
    assert await plant_names(client, gid) == ["Basil"]
    assert approved["result"]["plant_id"] == (await client.get(f"/gardens/{gid}/plants")).json()[0]["id"]
    assert (await run_db(lambda s: _event_types(s, gid)))[-3:] == ["request.created", "plant.created", "request.approved"]


async def test_admin_edits_then_approves(client):
    gid = await garden_with_contributor(client)
    req = await plant_request(client, gid, name="basel")
    login(sub="auth0|ann")
    edited = (await client.patch(url(gid, req["id"]), json={"payload": {"name": "Basil", "water_every_days": 2}})).json()
    assert edited["payload"]["name"] == "Basil"
    await client.post(url(gid, req["id"], "approve"), json={})
    [plant] = (await client.get(f"/gardens/{gid}/plants")).json()
    assert (plant["name"], plant["water_every_days"]) == ("Basil", 2)


async def test_admin_rejects(client):
    gid = await garden_with_contributor(client)
    req = await plant_request(client, gid)
    login(sub="auth0|ann")
    rejected = (await client.post(url(gid, req["id"], "reject"), json={"reason": "no room"})).json()
    assert (rejected["status"], rejected["decision_reason"]) == ("rejected", "no room")
    assert await plant_names(client, gid) == []


async def test_decided_requests_are_final(client):
    gid = await garden_with_contributor(client)
    req = await plant_request(client, gid)
    login(sub="auth0|ann")
    await client.post(url(gid, req["id"], "reject"), json={})
    assert (await client.post(url(gid, req["id"], "approve"), json={})).status_code == 409
    assert (await client.patch(url(gid, req["id"]), json={"note": "x"})).status_code == 409


async def test_requester_cancels_own_pending_request(client):
    gid = await garden_with_contributor(client)
    req = await plant_request(client, gid)
    login(sub="auth0|ann")
    assert (await client.post(url(gid, req["id"], "cancel"))).status_code == 403  # only the requester
    login(sub="auth0|bob")
    assert (await client.post(url(gid, req["id"], "cancel"))).json()["status"] == "cancelled"


async def test_contributor_cannot_decide_or_edit(client):
    gid = await garden_with_contributor(client)
    req = await plant_request(client, gid)
    assert (await client.post(url(gid, req["id"], "approve"), json={})).status_code == 403
    assert (await client.post(url(gid, req["id"], "reject"), json={})).status_code == 403
    assert (await client.patch(url(gid, req["id"]), json={"note": "x"})).status_code == 403


async def test_contributors_only_see_their_own_requests(client):
    gid = await garden_with_contributor(client)
    await onboard(client, "auth0|cat")
    await add_member(client, gid, "cat")
    bobs = await plant_request(client, gid)
    login(sub="auth0|cat")
    assert (await client.get(url(gid))).json() == []
    assert (await client.get(url(gid, bobs["id"]))).status_code == 404
    login(sub="auth0|ann")
    assert [r["id"] for r in (await client.get(url(gid), params={"status": "pending"})).json()] == [bobs["id"]]


async def test_admin_requests_are_auto_approved(client):
    gid = await garden_with_contributor(client)
    login(sub="auth0|ann")
    req = (await client.post(url(gid), json={"type": "create_plant", "payload": {"name": "Mint"}})).json()
    assert (req["status"], req["decided_by"]) == ("approved", "ann")
    assert await plant_names(client, gid) == ["Mint"]


async def test_invalid_requests_rejected_up_front(client):
    gid = await garden_with_contributor(client)
    login(sub="auth0|bob")
    assert (await client.post(url(gid), json={"type": "teleport", "payload": {}})).status_code == 400
    assert (await client.post(url(gid), json={"type": "create_plant", "payload": {"name": " "}})).status_code == 400
    assert (await client.post(url(gid), json={"type": "create_plant", "payload": {}})).status_code == 400
    long_note = {"type": "create_plant", "payload": {"name": "Basil"}, "note": "x" * 501}
    assert (await client.post(url(gid), json=long_note)).status_code == 400


async def test_global_admin_can_decide(client):
    gid = await garden_with_contributor(client)
    req = await plant_request(client, gid)
    login(GLOBAL_ADMIN, sub="auth0|root")
    assert (await client.post(url(gid, req["id"], "approve"), json={})).json()["status"] == "approved"
