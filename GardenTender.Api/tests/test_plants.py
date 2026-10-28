from sqlalchemy import select

from app.models import GardenEventRow
from tests.support import GLOBAL_ADMIN, garden_with_contributor, login, run_db


def plants_url(gid, plant_id=None):
    return f"/gardens/{gid}/plants" + (f"/{plant_id}" if plant_id else "")


async def _event_types(session, gid):
    query = select(GardenEventRow.type).where(GardenEventRow.garden_id == gid).order_by(GardenEventRow.id)
    return list(await session.scalars(query))


async def test_admin_creates_edits_deletes(client):
    gid = await garden_with_contributor(client)
    login(sub="auth0|ann")
    created = (await client.post(plants_url(gid), json={"name": " Fern ", "species": "Nephrolepis"})).json()
    assert created["name"] == "Fern"
    pid = created["id"]
    assert (await client.patch(plants_url(gid, pid), json={"field": "water_every_days", "value": "4"})).json()["water_every_days"] == 4
    assert (await client.delete(plants_url(gid, pid))).status_code == 204
    assert (await client.get(plants_url(gid))).json() == []
    assert (await run_db(lambda s: _event_types(s, gid)))[-3:] == ["plant.created", "plant.updated", "plant.deleted"]


async def test_contributor_edits_but_cannot_create_or_delete(client):
    gid = await garden_with_contributor(client)
    login(sub="auth0|ann")
    pid = (await client.post(plants_url(gid), json={"name": "Fern"})).json()["id"]
    login(sub="auth0|bob")
    assert (await client.patch(plants_url(gid, pid), json={"field": "notes", "value": "north window"})).status_code == 200
    assert (await client.post(plants_url(gid), json={"name": "Basil"})).status_code == 403
    assert (await client.delete(plants_url(gid, pid))).status_code == 403


async def test_plants_are_scoped_to_their_garden(client):
    gid = await garden_with_contributor(client)
    login(sub="auth0|ann")
    pid = (await client.post(plants_url(gid), json={"name": "Fern"})).json()["id"]
    other = (await client.post("/gardens", json={"name": "Other"})).json()["id"]
    assert (await client.patch(plants_url(other, pid), json={"field": "name", "value": "x"})).status_code == 404
    assert (await client.delete(plants_url(other, pid))).status_code == 404


async def test_validation_errors(client):
    gid = await garden_with_contributor(client)
    login(sub="auth0|ann")
    assert (await client.post(plants_url(gid), json={"name": "Fern", "water_every_days": 0})).status_code == 400
    assert (await client.post(plants_url(gid), json={"name": "  "})).status_code == 400
    pid = (await client.post(plants_url(gid), json={"name": "Fern"})).json()["id"]
    assert (await client.patch(plants_url(gid, pid), json={"field": "id", "value": "9"})).status_code == 400
    assert (await client.patch(plants_url(gid, 999), json={"field": "name", "value": "x"})).status_code == 404


async def test_global_admin_manages_plants_anywhere(client):
    gid = await garden_with_contributor(client)
    login(GLOBAL_ADMIN, sub="auth0|root")
    assert (await client.post(plants_url(gid), json={"name": "Fern"})).status_code == 201
