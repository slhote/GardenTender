from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.models import GardenEventRow, GardenMemberRow, GardenRow
from app.services import gardens
from tests.support import GLOBAL_ADMIN, create_garden, garden_with_contributor, login, onboard, run_db
from tests.support import add_member as add


async def _scalars(session, query):
    return list(await session.scalars(query))


async def _exec(session, stmt):
    await session.execute(stmt)
    await session.commit()


async def event_types(garden_id):
    query = select(GardenEventRow.type).where(GardenEventRow.garden_id == garden_id).order_by(GardenEventRow.id)
    return await run_db(lambda s: _scalars(s, query))


async def backdate_deletion(garden_id, days):
    when = datetime.now(UTC) - timedelta(days=days)
    await run_db(lambda s: _exec(s, update(GardenRow).where(GardenRow.id == garden_id).values(deleted_at=when)))


async def test_creating_a_garden_requires_onboarding(client):
    login(sub="auth0|new")
    assert (await client.post("/gardens", json={"name": "Backyard"})).status_code == 403


async def test_creator_becomes_admin(client):
    await onboard(client, "auth0|ann")
    gid = await create_garden(client, "auth0|ann")
    [mine] = (await client.get("/gardens")).json()
    assert (mine["id"], mine["name"], mine["my_role"], mine["deleted_at"]) == (gid, "Backyard", "admin", None)
    members = (await client.get(f"/gardens/{gid}/members")).json()
    assert [(m["handle"], m["role"]) for m in members] == [("ann", "admin")]
    assert await event_types(gid) == ["garden.created"]


async def test_non_members_get_404_not_403(client):
    await onboard(client, "auth0|ann")
    gid = await create_garden(client, "auth0|ann")
    await onboard(client, "auth0|bob")
    assert (await client.get(f"/gardens/{gid}")).status_code == 404
    assert (await client.get("/gardens/999")).status_code == 404


async def test_contributor_can_view_but_not_manage(client):
    gid = await garden_with_contributor(client)
    login(sub="auth0|bob")
    assert (await client.get(f"/gardens/{gid}")).json()["my_role"] == "contributor"
    assert (await client.patch(f"/gardens/{gid}", json={"name": "Mine"})).status_code == 403
    assert (await client.delete(f"/gardens/{gid}")).status_code == 403
    assert (await client.patch(f"/gardens/{gid}/members/ann", json={"role": "contributor"})).status_code == 403
    assert (await client.delete(f"/gardens/{gid}/members/ann")).status_code == 403


async def test_only_global_admin_adds_members_directly(client):
    await onboard(client, "auth0|ann")
    gid = await create_garden(client, "auth0|ann")
    await onboard(client, "auth0|bob")
    login(sub="auth0|ann")
    assert (await client.post(f"/gardens/{gid}/members", json={"handle": "bob"})).status_code == 403


async def test_adding_unknown_or_existing_member(client):
    gid = await garden_with_contributor(client)
    login(GLOBAL_ADMIN, sub="auth0|root")
    assert (await client.post(f"/gardens/{gid}/members", json={"handle": "nobody"})).status_code == 404
    assert (await client.post(f"/gardens/{gid}/members", json={"handle": "bob"})).status_code == 409


async def test_admin_manages_roles_and_members(client):
    gid = await garden_with_contributor(client)
    await onboard(client, "auth0|cat")
    await add(client, gid, "cat")
    login(sub="auth0|ann")
    assert (await client.patch(f"/gardens/{gid}/members/BOB", json={"role": "admin"})).json()["role"] == "admin"
    assert (await client.delete(f"/gardens/{gid}/members/cat")).status_code == 204
    assert (await event_types(gid))[-2:] == ["member.role_changed", "member.removed"]


async def test_last_admin_cannot_leave_or_be_demoted(client):
    await onboard(client, "auth0|ann")
    gid = await create_garden(client, "auth0|ann")
    login(sub="auth0|ann")
    assert (await client.patch(f"/gardens/{gid}/members/ann", json={"role": "contributor"})).status_code == 409
    assert (await client.delete(f"/gardens/{gid}/members/ann")).status_code == 409
    login(GLOBAL_ADMIN, sub="auth0|root")  # the invariant binds global admins too
    assert (await client.delete(f"/gardens/{gid}/members/ann")).status_code == 409


async def test_admin_can_leave_once_another_admin_exists(client):
    await onboard(client, "auth0|ann")
    gid = await create_garden(client, "auth0|ann")
    await onboard(client, "auth0|bob")
    await add(client, gid, "bob", role="admin")
    login(sub="auth0|ann")
    assert (await client.delete(f"/gardens/{gid}/members/ann")).status_code == 204
    assert (await client.get(f"/gardens/{gid}")).status_code == 404
    assert (await event_types(gid))[-1] == "member.left"


async def test_contributor_can_leave(client):
    gid = await garden_with_contributor(client)
    login(sub="auth0|bob")
    assert (await client.delete(f"/gardens/{gid}/members/bob")).status_code == 204


async def test_soft_delete_hides_and_restore_brings_back(client):
    await onboard(client, "auth0|ann")
    gid = await create_garden(client, "auth0|ann")
    login(sub="auth0|ann")
    assert (await client.delete(f"/gardens/{gid}")).status_code == 204
    assert (await client.get("/gardens")).json() == []
    assert (await client.get(f"/gardens/{gid}")).status_code == 404
    assert (await client.post(f"/gardens/{gid}/restore")).json()["deleted_at"] is None
    assert (await client.get(f"/gardens/{gid}")).status_code == 200
    assert (await event_types(gid))[-2:] == ["garden.deleted", "garden.restored"]


async def test_restore_refused_after_retention(client):
    await onboard(client, "auth0|ann")
    gid = await create_garden(client, "auth0|ann")
    login(sub="auth0|ann")
    await client.delete(f"/gardens/{gid}")
    await backdate_deletion(gid, days=16)
    assert (await client.post(f"/gardens/{gid}/restore")).status_code == 404


async def test_purge_removes_only_expired_gardens(client):
    await onboard(client, "auth0|ann")
    expired = await create_garden(client, "auth0|ann", "Old")
    recent = await create_garden(client, "auth0|ann", "New")
    login(sub="auth0|ann")
    await client.delete(f"/gardens/{expired}")
    await client.delete(f"/gardens/{recent}")
    await backdate_deletion(expired, days=16)

    assert await run_db(lambda s: gardens.purge_deleted(s, retention_days=15)) == 1
    assert await run_db(lambda s: _scalars(s, select(GardenRow.id))) == [recent]
    assert await run_db(lambda s: _scalars(s, select(GardenMemberRow.garden_id))) == [recent]
    assert await event_types(expired) == []


async def test_global_admin_can_manage_any_garden(client):
    await onboard(client, "auth0|ann")
    gid = await create_garden(client, "auth0|ann")
    login(GLOBAL_ADMIN, sub="auth0|root")
    assert (await client.get(f"/gardens/{gid}")).json()["my_role"] is None
    assert (await client.patch(f"/gardens/{gid}", json={"name": "Renamed"})).status_code == 200
    [event] = await run_db(lambda s: _scalars(s, select(GardenEventRow).where(GardenEventRow.type == "garden.renamed")))
    assert event.via_global_admin is True and event.actor_sub == "auth0|root"


async def test_garden_name_validated(client):
    await onboard(client, "auth0|ann")
    login(sub="auth0|ann")
    assert (await client.post("/gardens", json={"name": "   "})).status_code == 400
    assert (await client.post("/gardens", json={"name": "x" * 61})).status_code == 400


async def test_member_list_shows_inviter(client):
    gid = await garden_with_contributor(client)
    stmt = update(GardenMemberRow).where(GardenMemberRow.user_sub == "auth0|bob").values(invited_by="auth0|ann")
    await run_db(lambda s: _exec(s, stmt))
    login(sub="auth0|ann")
    bob = next(m for m in (await client.get(f"/gardens/{gid}/members")).json() if m["handle"] == "bob")
    assert bob["invited_by"] == "ann"
