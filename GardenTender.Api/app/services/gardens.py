"""Gardens and their members. Authorization is resolved before these run (app.services.access);
these functions enforce the garden's own rules, e.g. a garden always keeps at least one admin.
"""
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.access import Actor, GardenAccess
from app.errors import Conflict, Forbidden, NotFound
from app.models import GardenEventRow, GardenMemberRow, GardenRequestRow, GardenRow, PlantRow, UserRow
from app.roles import GardenPermission, GardenRole, role_allows
from app.services import events, users
from app.services.text import normalize_name

NAME_MAX = 60


class GardenOut(BaseModel):
    id: int
    name: str
    created_at: datetime
    deleted_at: datetime | None = None
    my_role: GardenRole | None = None


class MemberOut(BaseModel):
    handle: str
    display_name: str
    role: GardenRole
    joined_at: datetime
    invited_by: str | None = None  # handle of the inviter: "joined via invite from X"


def _out(garden: GardenRow, role: GardenRole | str | None = None) -> GardenOut:
    return GardenOut(
        id=garden.id,
        name=garden.name,
        created_at=garden.created_at,
        deleted_at=garden.deleted_at,
        my_role=GardenRole(role) if role else None,
    )


def to_out(access: GardenAccess) -> GardenOut:
    return _out(access.garden, access.role)


async def create(session: AsyncSession, actor: Actor, name: str) -> GardenOut:
    """The creator becomes the garden's first admin."""
    garden = GardenRow(name=normalize_name(name, "Garden name", NAME_MAX), created_by=actor.sub)
    session.add(garden)
    await session.flush()
    session.add(GardenMemberRow(garden_id=garden.id, user_sub=actor.sub, role=GardenRole.ADMIN))
    events.record(session, garden.id, actor, "garden.created", name=garden.name)
    await session.commit()
    return _out(garden, GardenRole.ADMIN)


async def list_mine(session: AsyncSession, sub: str) -> list[GardenOut]:
    rows = await session.execute(
        select(GardenRow, GardenMemberRow.role)
        .join(GardenMemberRow, GardenMemberRow.garden_id == GardenRow.id)
        .where(GardenMemberRow.user_sub == sub, GardenRow.deleted_at.is_(None))
        .order_by(GardenRow.name)
    )
    return [_out(g, role) for g, role in rows]


async def list_all(session: AsyncSession, include_deleted: bool) -> list[GardenOut]:
    query = select(GardenRow).order_by(GardenRow.id)
    if not include_deleted:
        query = query.where(GardenRow.deleted_at.is_(None))
    return [_out(g) for g in await session.scalars(query)]


async def rename(session: AsyncSession, access: GardenAccess, name: str) -> GardenOut:
    garden = access.garden
    old, garden.name = garden.name, normalize_name(name, "Garden name", NAME_MAX)
    events.record(session, garden.id, access.actor, "garden.renamed", old=old, new=garden.name)
    await session.commit()
    return to_out(access)


async def soft_delete(session: AsyncSession, access: GardenAccess, now: datetime | None = None) -> None:
    garden = access.garden
    if garden.deleted_at is None:
        garden.deleted_at = now or datetime.now(UTC)
        events.record(session, garden.id, access.actor, "garden.deleted")
        await session.commit()


async def restore(session: AsyncSession, access: GardenAccess, retention_days: int, now: datetime | None = None) -> GardenOut:
    garden = access.garden
    if garden.deleted_at is None:
        return to_out(access)
    if _as_utc(garden.deleted_at) < (now or datetime.now(UTC)) - timedelta(days=retention_days):
        raise NotFound("Garden not found.")  # past retention: waiting to be purged
    garden.deleted_at = None
    events.record(session, garden.id, access.actor, "garden.restored")
    await session.commit()
    return to_out(access)


async def purge_deleted(session: AsyncSession, retention_days: int, now: datetime | None = None) -> int:
    """Hard-deletes gardens soft-deleted more than `retention_days` ago, with their plants, members and history."""
    cutoff = (now or datetime.now(UTC)) - timedelta(days=retention_days)
    ids = list(await session.scalars(select(GardenRow.id).where(GardenRow.deleted_at < cutoff)))
    if ids:
        # Explicit child deletes so this doesn't depend on the database enforcing ON DELETE CASCADE.
        await session.execute(delete(GardenRequestRow).where(GardenRequestRow.garden_id.in_(ids)))
        await session.execute(delete(PlantRow).where(PlantRow.garden_id.in_(ids)))
        await session.execute(delete(GardenEventRow).where(GardenEventRow.garden_id.in_(ids)))
        await session.execute(delete(GardenMemberRow).where(GardenMemberRow.garden_id.in_(ids)))
        await session.execute(delete(GardenRow).where(GardenRow.id.in_(ids)))
        await session.commit()
    return len(ids)


async def list_members(session: AsyncSession, garden_id: int) -> list[MemberOut]:
    inviter = aliased(UserRow)
    rows = await session.execute(
        select(GardenMemberRow, UserRow, inviter.handle)
        .join(UserRow, UserRow.sub == GardenMemberRow.user_sub)
        .outerjoin(inviter, inviter.sub == GardenMemberRow.invited_by)
        .where(GardenMemberRow.garden_id == garden_id)
        .order_by(UserRow.handle)
    )
    return [
        MemberOut(handle=u.handle, display_name=u.display_name, role=m.role, joined_at=m.joined_at, invited_by=inv)
        for m, u, inv in rows
    ]


async def add_member(session: AsyncSession, access: GardenAccess, handle: str, role: GardenRole) -> MemberOut:
    """Direct add, bypassing invites (global admin only, via GardenPermission.ADD_MEMBER_DIRECTLY)."""
    user = await users.get_by_handle(session, handle)
    if user is None or not users.is_onboarded(user):
        raise NotFound(f"No user @{handle}.")
    if await session.get(GardenMemberRow, (access.garden.id, user.sub)) is not None:
        raise Conflict(f"@{user.handle} is already a member.")
    member = GardenMemberRow(garden_id=access.garden.id, user_sub=user.sub, role=role)
    session.add(member)
    events.record(session, access.garden.id, access.actor, "member.added", handle=user.handle, role=role)
    await session.commit()
    return MemberOut(handle=user.handle, display_name=user.display_name, role=role, joined_at=member.joined_at)


async def change_role(session: AsyncSession, access: GardenAccess, handle: str, role: GardenRole) -> MemberOut:
    await _lock(session, access.garden.id)
    user, member = await _member(session, access.garden.id, handle)
    if member.role == GardenRole.ADMIN and role != GardenRole.ADMIN:
        await _ensure_not_last_admin(session, access.garden.id)
    if member.role != role:
        events.record(session, access.garden.id, access.actor, "member.role_changed", handle=user.handle, old=member.role, new=role)
        member.role = role
    await session.commit()
    return MemberOut(handle=user.handle, display_name=user.display_name, role=role, joined_at=member.joined_at)


async def remove_member(session: AsyncSession, access: GardenAccess, handle: str) -> None:
    """Members may always remove themselves (leave); removing others needs members:manage."""
    await _lock(session, access.garden.id)
    user, member = await _member(session, access.garden.id, handle)
    leaving = user.sub == access.user.sub
    if not leaving and not (access.via_global_admin or role_allows(access.role, GardenPermission.MANAGE_MEMBERS)):
        raise Forbidden("Your role in this garden doesn't allow that.")
    if member.role == GardenRole.ADMIN:
        await _ensure_not_last_admin(session, access.garden.id)
    await session.delete(member)
    events.record(session, access.garden.id, access.actor, "member.left" if leaving else "member.removed", handle=user.handle)
    await session.commit()


async def _lock(session: AsyncSession, garden_id: int) -> None:
    """Serializes membership changes per garden, so two concurrent demotions can't remove the last admin."""
    await session.scalar(select(GardenRow.id).where(GardenRow.id == garden_id).with_for_update())


async def _member(session: AsyncSession, garden_id: int, handle: str) -> tuple[UserRow, GardenMemberRow]:
    user = await users.get_by_handle(session, handle)
    member = await session.get(GardenMemberRow, (garden_id, user.sub)) if user else None
    if member is None:
        raise NotFound(f"@{handle} is not a member of this garden.")
    return user, member


async def _ensure_not_last_admin(session: AsyncSession, garden_id: int) -> None:
    admins = await session.scalar(
        select(func.count()).where(GardenMemberRow.garden_id == garden_id, GardenMemberRow.role == GardenRole.ADMIN)
    )
    if admins <= 1:
        raise Conflict("A garden must keep at least one admin. Promote someone else first.")


def _as_utc(value: datetime) -> datetime:
    # SQLite returns naive datetimes; Postgres returns aware ones.
    return value if value.tzinfo else value.replace(tzinfo=UTC)

