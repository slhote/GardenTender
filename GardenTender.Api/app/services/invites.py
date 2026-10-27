"""Garden invites.

An invite is a single-use bearer token (stored hashed) with an expiry, revocable by admins. Whoever holds the
link may accept it with any account: invitees often sign up with a different email than the one invited.
Invites to an existing user (found by handle, or whose email matches) also show up in their in-app list,
where they can accept without the token.
"""
import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from pydantic import BaseModel, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.access import Actor, GardenAccess
from app.errors import Conflict, Forbidden, NotFound
from app.models import GardenMemberRow, GardenRow, InviteRow, UserRow
from app.roles import GardenRole
from app.services import events, users
from app.services.notifier import Notifier

EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


class InviteVia(StrEnum):
    HANDLE = "handle"
    EMAIL = "email"
    QR = "qr"


class InviteTarget(BaseModel):
    """Who to invite: exactly one of an existing user's handle or an email address."""

    handle: str | None = None
    email: str | None = None
    role: GardenRole = GardenRole.CONTRIBUTOR

    @model_validator(mode="after")
    def _one_target(self):
        if (self.handle is None) == (self.email is None):
            raise ValueError("Give exactly one of handle or email.")
        if self.email is not None:
            self.email = self.email.strip().lower()
            if not EMAIL_RE.fullmatch(self.email):
                raise ValueError("Not a valid email address.")
        return self


class InviteOut(BaseModel):
    """What garden admins see. Never reveals an existing user's email, or which user an email belongs to."""

    id: int
    via: InviteVia
    handle: str | None  # only for invites made by handle
    email: str | None  # only the address the inviter typed
    role: GardenRole
    invited_by: str | None
    expires_at: datetime


class CreatedQrInvite(BaseModel):
    id: int
    url: str  # encode this in the QR code
    role: GardenRole
    expires_at: datetime


class MyInvite(BaseModel):
    id: int
    garden_id: int
    garden_name: str
    role: GardenRole
    invited_by: str | None
    expires_at: datetime


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _new_token() -> str:
    return secrets.token_urlsafe(32)


def _now() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    # SQLite returns naive datetimes; Postgres returns aware ones.
    return value if value.tzinfo else value.replace(tzinfo=UTC)


async def create(
    session: AsyncSession,
    garden: GardenRow,
    actor: Actor,
    target: InviteTarget,
    notifier: Notifier,
    ttl: timedelta,
) -> InviteOut:
    """Creates and queues the invite email (sent after the caller commits). Does not commit."""
    invitee: UserRow | None = None
    if target.handle is not None:
        invitee = await users.get_by_handle(session, target.handle)
        if invitee is None or not users.is_onboarded(invitee):
            raise NotFound(f"No user @{target.handle}.")
        if await session.get(GardenMemberRow, (garden.id, invitee.sub)) is not None:
            raise Conflict(f"@{invitee.handle} is already a member.")
    else:
        # A matching account sees the invite in-app too; the inviter is never told the address has an account.
        invitee = await session.scalar(select(UserRow).where(UserRow.email == target.email))

    token = _new_token()
    via = InviteVia.HANDLE if target.handle is not None else InviteVia.EMAIL
    row = InviteRow(
        garden_id=garden.id,
        token_hash=hash_token(token),
        via=via,
        role=target.role,
        invited_by=actor.sub,
        invitee_sub=invitee.sub if invitee else None,
        email=target.email,
        expires_at=_now() + ttl,
    )
    session.add(row)
    await session.flush()
    events.record(
        session, garden.id, actor, "invite.created", invite_id=row.id, via=via, role=target.role,
        **({"handle": invitee.handle} if via == InviteVia.HANDLE else {"email": target.email}),
    )

    send_to = target.email or (invitee.email if invitee else None)
    if send_to:
        inviter = await session.get(UserRow, actor.sub)
        inviter_name = f"@{inviter.handle}" if inviter and inviter.handle else "Someone"
        notifier.queue_email(
            send_to,
            f"You're invited to {garden.name} on GardenTender",
            f"{inviter_name} invited you to join the garden \"{garden.name}\" as {target.role}.\n\n"
            f"Accept the invite: {notifier.links.invite(token)}\n\n"
            f"The link works once and expires on {row.expires_at:%Y-%m-%d}.",
        )
    return await _out(session, row)


async def create_qr(session: AsyncSession, access: GardenAccess, role: GardenRole, notifier: Notifier, ttl: timedelta) -> CreatedQrInvite:
    """Short-lived single-use invite shown as a QR code for someone standing next to the admin."""
    token = _new_token()
    row = InviteRow(
        garden_id=access.garden.id,
        token_hash=hash_token(token),
        via=InviteVia.QR,
        role=role,
        invited_by=access.user.sub,
        expires_at=_now() + ttl,
    )
    session.add(row)
    await session.flush()
    events.record(session, access.garden.id, access.actor, "invite.created", invite_id=row.id, via=InviteVia.QR, role=role)
    await session.commit()
    return CreatedQrInvite(id=row.id, url=notifier.links.invite(token), role=role, expires_at=row.expires_at)


async def list_pending(session: AsyncSession, garden_id: int) -> list[InviteOut]:
    rows = await session.scalars(_pending_query().where(InviteRow.garden_id == garden_id).order_by(InviteRow.id))
    return [await _out(session, r) for r in rows]


async def revoke(session: AsyncSession, access: GardenAccess, invite_id: int) -> None:
    row = await session.scalar(select(InviteRow).where(InviteRow.id == invite_id, InviteRow.garden_id == access.garden.id))
    if row is None:
        raise NotFound("Invite not found.")
    if row.revoked_at is None and row.accepted_at is None:
        row.revoked_at = _now()
        events.record(session, access.garden.id, access.actor, "invite.revoked", invite_id=row.id)
        await session.commit()


async def mine(session: AsyncSession, sub: str) -> list[MyInvite]:
    inviter = aliased(UserRow)
    rows = await session.execute(
        _pending_query()
        .add_columns(GardenRow.name, inviter.handle)
        .join(GardenRow, GardenRow.id == InviteRow.garden_id)
        .outerjoin(inviter, inviter.sub == InviteRow.invited_by)
        .where(InviteRow.invitee_sub == sub, GardenRow.deleted_at.is_(None))
        .order_by(InviteRow.id)
    )
    return [
        MyInvite(id=r.id, garden_id=r.garden_id, garden_name=name, role=r.role, invited_by=inv, expires_at=r.expires_at)
        for r, name, inv in rows
    ]


async def accept_token(session: AsyncSession, account: UserRow, token: str) -> int:
    """Accepts with the link's token. Returns the garden id."""
    row = await session.scalar(select(InviteRow).where(InviteRow.token_hash == hash_token(token)).with_for_update())
    return await _accept(session, row, account)


async def accept_mine(session: AsyncSession, account: UserRow, invite_id: int) -> int:
    row = await _mine_locked(session, account, invite_id)
    return await _accept(session, row, account)


async def decline_mine(session: AsyncSession, account: UserRow, invite_id: int) -> None:
    row = await _mine_locked(session, account, invite_id)
    _check_usable(row)
    row.declined_at = _now()
    events.record(session, row.garden_id, Actor(account.sub), "invite.declined", invite_id=row.id)
    await session.commit()


async def _mine_locked(session: AsyncSession, account: UserRow, invite_id: int) -> InviteRow | None:
    row = await session.scalar(select(InviteRow).where(InviteRow.id == invite_id).with_for_update())
    if row is not None and row.invitee_sub != account.sub:
        return None  # someone else's invite: same answer as a missing one
    return row


async def _accept(session: AsyncSession, row: InviteRow | None, account: UserRow) -> int:
    if not users.is_onboarded(account):
        raise Forbidden("Finish your profile (handle and display name) first.")
    _check_usable(row)
    garden = await session.get(GardenRow, row.garden_id)
    if garden is None or garden.deleted_at is not None:
        raise NotFound("This invite is no longer valid.")
    if await session.get(GardenMemberRow, (garden.id, account.sub)) is not None:
        raise Conflict("You're already a member of this garden.")
    row.accepted_at, row.accepted_by = _now(), account.sub
    session.add(GardenMemberRow(garden_id=garden.id, user_sub=account.sub, role=row.role, invited_by=row.invited_by))
    events.record(session, garden.id, Actor(account.sub), "member.joined", invite_id=row.id, handle=account.handle, role=row.role)
    await session.commit()
    return garden.id


def _check_usable(row: InviteRow | None) -> None:
    # One message for every unusable state: a token holder learns nothing about why.
    if (
        row is None
        or row.accepted_at is not None
        or row.revoked_at is not None
        or row.declined_at is not None
        or _as_utc(row.expires_at) <= _now()
    ):
        raise NotFound("This invite is no longer valid.")


def _pending_query():
    return select(InviteRow).where(
        InviteRow.accepted_at.is_(None),
        InviteRow.revoked_at.is_(None),
        InviteRow.declined_at.is_(None),
        InviteRow.expires_at > _now(),
    )


async def _out(session: AsyncSession, row: InviteRow) -> InviteOut:
    invitee = await session.get(UserRow, row.invitee_sub) if row.via == InviteVia.HANDLE and row.invitee_sub else None
    inviter = await session.get(UserRow, row.invited_by) if row.invited_by else None
    return InviteOut(
        id=row.id,
        via=row.via,
        handle=invitee.handle if invitee else None,
        email=row.email,
        role=row.role,
        invited_by=inviter.handle if inviter else None,
        expires_at=row.expires_at,
    )

