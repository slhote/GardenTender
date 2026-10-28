from sqlalchemy import select

from app.models import GardenEventRow
from tests.support import GLOBAL_ADMIN, garden_with_contributor, login, run_db


def plants_url(gid, plant_id=None):
    return f"/gardens/{gid}/plants" + (f"/{plant_id}" if plant_id else "")


async def _event_types(session, gid):
    query = select(GardenEventRow.type).where(GardenEventRow.garden_id == gid).order_by(GardenEventRow.id)
    return list(await session.scalars(query))


def test_admin_creates_edits_deletes(client):
    gid = garden_with_contributor(client)
    login(sub="auth0|ann")
    created = client.post(plants_url(gid), json={"name": " Fern ", "species": "Nephrolepis"}).json()
    assert created["name"] == "Fern"
    pid = created["id"]
    assert client.patch(plants_url(gid, pid), json={"field": "water_every_days", "value": "4"}).json()["water_every_days"] == 4
    assert client.delete(plants_url(gid, pid)).status_code == 204
    assert client.get(plants_url(gid)).json() == []
    assert run_db(lambda s: _event_types(s, gid))[-3:] == ["plant.created", "plant.updated", "plant.deleted"]


def test_contributor_edits_but_cannot_create_or_delete(client):
    gid = garden_with_contributor(client)
    login(sub="auth0|ann")
    pid = client.post(plants_url(gid), json={"name": "Fern"}).json()["id"]
    login(sub="auth0|bob")
    assert client.patch(plants_url(gid, pid), json={"field": "notes", "value": "north window"}).status_code == 200
    assert client.post(plants_url(gid), json={"name": "Basil"}).status_code == 403
    assert client.delete(plants_url(gid, pid)).status_code == 403


def test_plants_are_scoped_to_their_garden(client):
    gid = garden_with_contributor(client)
    login(sub="auth0|ann")
    pid = client.post(plants_url(gid), json={"name": "Fern"}).json()["id"]
    other = client.post("/gardens", json={"name": "Other"}).json()["id"]
    assert client.patch(plants_url(other, pid), json={"field": "name", "value": "x"}).status_code == 404
    assert client.delete(plants_url(other, pid)).status_code == 404


def test_validation_errors(client):
    gid = garden_with_contributor(client)
    login(sub="auth0|ann")
    assert client.post(plants_url(gid), json={"name": "Fern", "water_every_days": 0}).status_code == 400
    assert client.post(plants_url(gid), json={"name": "  "}).status_code == 400
    pid = client.post(plants_url(gid), json={"name": "Fern"}).json()["id"]
    assert client.patch(plants_url(gid, pid), json={"field": "id", "value": "9"}).status_code == 400
    assert client.patch(plants_url(gid, 999), json={"field": "name", "value": "x"}).status_code == 404


def test_global_admin_manages_plants_anywhere(client):
    gid = garden_with_contributor(client)
    login(GLOBAL_ADMIN, sub="auth0|root")
    assert client.post(plants_url(gid), json={"name": "Fern"}).status_code == 201
