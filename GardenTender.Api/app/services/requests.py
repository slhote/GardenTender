"""Approval requests: a member asks for something their role can't do directly, and an admin decides.

Each request type is a `RequestKind` in `KINDS` (validate the payload, apply it on approval). Adding a type
means adding a kind; the submit/edit/approve/reject/cancel flow doesn't change. Members whose role already
holds the kind's direct permission (admins) are auto-approved: the request is recorded and applied at once.
"""
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.access import Actor, GardenAccess
from app.errors import Conflict, Forbidden, InvalidInput, NotFound
from app.models import GardenRequestRow, GardenRow, UserRow
from app.roles import GardenPermission, GardenRole, role_allows
from app.services import events, invites, plants
from app.services.notifier import Notifier

NOTE_MAX = 500


class RequestStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class RequestDeps:
    """Collaborators a request may need when applied. Injected by the caller (router or chat)."""

    notifier: Notifier
    invite_ttl: timedelta


@dataclass(frozen=True)
class ApplyContext:
    session: AsyncSession
    garden: GardenRow
    actor: Actor
    deps: RequestDeps


@dataclass(frozen=True)
class RequestKind:
    direct_permission: GardenPermission  # holders skip the queue
    validate: Callable[[dict], dict]  # returns the normalized payload; raises InvalidInput
    apply: Callable[[ApplyContext, dict], Awaitable[dict]]  # runs on approval, without committing; returns `result`


def _model_payload(model: type[BaseModel], normalize: Callable[[BaseModel], BaseModel] = lambda m: m) -> Callable[[dict], dict]:
    def validate(payload: dict) -> dict:
        try:
            return normalize(model.model_validate(payload)).model_dump()
        except ValidationError as e:
            raise InvalidInput(f"Invalid request: {e.errors(include_url=False, include_context=False)}")

    return validate


async def _apply_create_plant(ctx: ApplyContext, payload: dict) -> dict:
    plant = await plants.create_plant(ctx.session, ctx.garden.id, ctx.actor, plants.NewPlant(**payload), commit=False)
    return {"plant_id": plant.id}


async def _apply_invite(ctx: ApplyContext, payload: dict) -> dict:
    target = invites.InviteTarget.model_validate(payload)
    invite = await invites.create(ctx.session, ctx.garden, ctx.actor, target, ctx.deps.notifier, ctx.deps.invite_ttl)
    return {"invite_id": invite.id}


KINDS: dict[str, RequestKind] = {
    "create_plant": RequestKind(
        direct_permission=GardenPermission.PLANTS_CREATE,
        validate=_model_payload(plants.NewPlant, plants.validate_new),
        apply=_apply_create_plant,
    ),
    # A contributor names who to invite; role defaults to contributor and the admin may change it before approving.
    "invite_user": RequestKind(
        direct_permission=GardenPermission.INVITE,
        validate=_model_payload(invites.InviteTarget),
        apply=_apply_invite,
    ),
}


class RequestOut(BaseModel):
    id: int
    type: str
    payload: dict
    note: str | None
    status: RequestStatus
    requested_by: str | None  # handle
    decided_by: str | None  # handle
    decided_at: datetime | None
    decision_reason: str | None
    result: dict | None
    created_at: datetime


def _kind(type: str) -> RequestKind:
    kind = KINDS.get(type)
    if kind is None:
        raise InvalidInput(f"Unknown request type {type!r}. Expected one of {sorted(KINDS)}.")
    return kind


def _text(value: str | None, label: str) -> str | None:
    if value is None or not value.strip():
        return None
    value = value.strip()
    if len(value) > NOTE_MAX:
        raise InvalidInput(f"{label} must be at most {NOTE_MAX} characters.")
    return value


async def submit(
    session: AsyncSession,
    garden_id: int,
    actor: Actor,
    role: GardenRole | None,
    type: str,
    payload: dict,
    note: str | None,
    deps: RequestDeps,
) -> RequestOut:
    kind = _kind(type)
    row = GardenRequestRow(
        garden_id=garden_id,
        type=type,
        payload=kind.validate(payload),
        note=_text(note, "Note"),
        status=RequestStatus.PENDING,
        requested_by=actor.sub,
    )
    session.add(row)
    await session.flush()
    events.record(session, garden_id, actor, "request.created", request_id=row.id, type=type)
    if actor.via_global_admin or (role is not None and role_allows(role, kind.direct_permission)):
        await _approve(session, row, kind, actor, None, deps)
    await session.commit()
    await deps.notifier.flush()
    return await get(session, garden_id, row.id)


async def list_requests(session: AsyncSession, access: GardenAccess, status: RequestStatus | None) -> list[RequestOut]:
    """Deciders see every request; everyone else sees only their own."""
    query = _select().where(GardenRequestRow.garden_id == access.garden.id).order_by(GardenRequestRow.id.desc())
    if status is not None:
        query = query.where(GardenRequestRow.status == status)
    if not _can_decide(access):
        query = query.where(GardenRequestRow.requested_by == access.user.sub)
    return [_out(*r) for r in await session.execute(query)]


async def get_visible(session: AsyncSession, access: GardenAccess, request_id: int) -> RequestOut:
    request = await get(session, access.garden.id, request_id)
    row = await session.get(GardenRequestRow, request_id)
    if not _can_decide(access) and row.requested_by != access.user.sub:
        raise NotFound("Request not found.")
    return request


async def get(session: AsyncSession, garden_id: int, request_id: int) -> RequestOut:
    found = (await session.execute(_select().where(GardenRequestRow.id == request_id, GardenRequestRow.garden_id == garden_id))).first()
    if found is None:
        raise NotFound("Request not found.")
    return _out(*found)


async def edit(session: AsyncSession, access: GardenAccess, request_id: int, payload: dict | None, note: str | None) -> RequestOut:
    """Deciders may adjust a pending request before deciding (e.g. fix a name, change an invite's role)."""
    row = await _pending(session, access.garden.id, request_id)
    changed = []
    if payload is not None:
        row.payload = _kind(row.type).validate(payload)
        changed.append("payload")
    if note is not None:
        row.note = _text(note, "Note")
        changed.append("note")
    if changed:
        events.record(session, access.garden.id, access.actor, "request.edited", request_id=row.id, fields=changed)
    await session.commit()
    return await get(session, access.garden.id, row.id)


async def approve(
    session: AsyncSession, access: GardenAccess, request_id: int, reason: str | None, deps: RequestDeps
) -> RequestOut:
    row = await _pending(session, access.garden.id, request_id)
    await _approve(session, row, _kind(row.type), access.actor, _text(reason, "Reason"), deps)
    await session.commit()
    await deps.notifier.flush()
    return await get(session, access.garden.id, row.id)


async def reject(session: AsyncSession, access: GardenAccess, request_id: int, reason: str | None) -> RequestOut:
    row = await _pending(session, access.garden.id, request_id)
    _decide(row, RequestStatus.REJECTED, access.actor, _text(reason, "Reason"))
    events.record(session, access.garden.id, access.actor, "request.rejected", request_id=row.id, reason=row.decision_reason)
    await session.commit()
    return await get(session, access.garden.id, row.id)


async def cancel(session: AsyncSession, access: GardenAccess, request_id: int) -> RequestOut:
    """Only the requester can withdraw their own pending request."""
    row = await _pending(session, access.garden.id, request_id)
    if row.requested_by != access.user.sub:
        raise Forbidden("Only the requester can cancel a request.")
    row.status = RequestStatus.CANCELLED
    events.record(session, access.garden.id, access.actor, "request.cancelled", request_id=row.id)
    await session.commit()
    return await get(session, access.garden.id, row.id)


async def _approve(
    session: AsyncSession, row: GardenRequestRow, kind: RequestKind, actor: Actor, reason: str | None, deps: RequestDeps
) -> None:
    garden = await session.get(GardenRow, row.garden_id)
    row.result = await kind.apply(ApplyContext(session, garden, actor, deps), row.payload)
    _decide(row, RequestStatus.APPROVED, actor, reason)
    events.record(session, row.garden_id, actor, "request.approved", request_id=row.id, reason=reason, result=row.result)


def _decide(row: GardenRequestRow, status: RequestStatus, actor: Actor, reason: str | None) -> None:
    row.status = status
    row.decided_by = actor.sub
    row.decided_at = datetime.now(UTC)
    row.decision_reason = reason


async def _pending(session: AsyncSession, garden_id: int, request_id: int) -> GardenRequestRow:
    """Locks the request so two admins can't both decide it."""
    row = await session.scalar(
        select(GardenRequestRow)
        .where(GardenRequestRow.id == request_id, GardenRequestRow.garden_id == garden_id)
        .with_for_update()
    )
    if row is None:
        raise NotFound("Request not found.")
    if row.status != RequestStatus.PENDING:
        raise Conflict(f"Request is already {row.status}.")
    return row


def _can_decide(access: GardenAccess) -> bool:
    return access.via_global_admin or (access.role is not None and role_allows(access.role, GardenPermission.DECIDE_REQUESTS))


def _select():
    requester, decider = aliased(UserRow), aliased(UserRow)
    return (
        select(GardenRequestRow, requester.handle, decider.handle)
        .outerjoin(requester, requester.sub == GardenRequestRow.requested_by)
        .outerjoin(decider, decider.sub == GardenRequestRow.decided_by)
    )


def _out(row: GardenRequestRow, requester: str | None, decider: str | None) -> RequestOut:
    return RequestOut(
        id=row.id,
        type=row.type,
        payload=row.payload,
        note=row.note,
        status=row.status,
        requested_by=requester,
        decided_by=decider,
        decided_at=row.decided_at,
        decision_reason=row.decision_reason,
        result=row.result,
        created_at=row.created_at,
    )
