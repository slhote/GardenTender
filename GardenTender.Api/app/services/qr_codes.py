"""Printable QR codes for a garden or one of its plants.

Every code is dynamic: it encodes only `<PUBLIC_BASE_URL>/q/<token>`, and the API resolves the token to its
current target. Admins can retarget, relabel or delete a code without reprinting anything; the URL is built
at render time, never stored. Invite QR codes are not here: they are short-lived invites (app.services.invites).
"""
import secrets
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.access import GardenAccess
from app.auth import User
from app.errors import InvalidInput, NotFound
from app.models import GardenMemberRow, GardenRow, PlantRow, QrCodeRow
from app.roles import GardenPermission, role_allows
from app.services import events
from app.services.notifier import Links
from app.services.text import normalize_name

LABEL_MAX = 60
NO_ACCESS = "QR code not found, or you don't have access to it."


class QrTarget(StrEnum):
    GARDEN = "garden"
    PLANT = "plant"


class QrIn(BaseModel):
    target_type: QrTarget
    plant_id: int | None = None
    label: str | None = None

    @model_validator(mode="after")
    def _plant_matches_type(self):
        if (self.target_type == QrTarget.PLANT) != (self.plant_id is not None):
            raise ValueError("plant_id is required for plant codes and not allowed otherwise.")
        return self


class QrPatch(BaseModel):
    label: str | None = None
    target: QrIn | None = None  # retarget the printed code


class QrOut(BaseModel):
    id: int
    url: str  # encode this in the QR code
    target_type: QrTarget
    plant_id: int | None
    label: str | None
    created_at: datetime


class Resolved(BaseModel):
    target_type: QrTarget
    garden_id: int
    plant_id: int | None


def _token() -> str:
    return secrets.token_urlsafe(9)  # 12 characters: short enough for a small, easily scanned code


def _label(value: str | None) -> str | None:
    return normalize_name(value, "Label", LABEL_MAX) if value and value.strip() else None


async def _check_target(session: AsyncSession, garden_id: int, target: QrIn) -> None:
    if target.plant_id is not None:
        plant = await session.scalar(select(PlantRow).where(PlantRow.id == target.plant_id, PlantRow.garden_id == garden_id))
        if plant is None:
            raise InvalidInput(f"No plant with id {target.plant_id} in this garden.")


def _out(row: QrCodeRow, links: Links) -> QrOut:
    return QrOut(
        id=row.id,
        url=links.qr(row.token),
        target_type=row.target_type,
        plant_id=row.plant_id,
        label=row.label,
        created_at=row.created_at,
    )


async def create(session: AsyncSession, access: GardenAccess, body: QrIn, links: Links) -> QrOut:
    await _check_target(session, access.garden.id, body)
    row = QrCodeRow(
        token=_token(),
        garden_id=access.garden.id,
        target_type=body.target_type,
        plant_id=body.plant_id,
        label=_label(body.label),
        created_by=access.user.sub,
    )
    session.add(row)
    await session.flush()
    events.record(session, access.garden.id, access.actor, "qr.created", qr_id=row.id, target_type=row.target_type, plant_id=row.plant_id)
    await session.commit()
    return _out(row, links)


async def list_codes(session: AsyncSession, garden_id: int, links: Links) -> list[QrOut]:
    rows = await session.scalars(select(QrCodeRow).where(QrCodeRow.garden_id == garden_id).order_by(QrCodeRow.id))
    return [_out(r, links) for r in rows]


async def update(session: AsyncSession, access: GardenAccess, qr_id: int, patch: QrPatch, links: Links) -> QrOut:
    row = await _get(session, access.garden.id, qr_id)
    changes = {}
    if patch.label is not None:
        row.label = changes["label"] = _label(patch.label)
    if patch.target is not None:
        await _check_target(session, access.garden.id, patch.target)
        row.target_type, row.plant_id = patch.target.target_type, patch.target.plant_id
        changes.update(target_type=row.target_type, plant_id=row.plant_id)
    if changes:
        events.record(session, access.garden.id, access.actor, "qr.updated", qr_id=row.id, **changes)
    await session.commit()
    return _out(row, links)


async def delete(session: AsyncSession, access: GardenAccess, qr_id: int) -> None:
    row = await _get(session, access.garden.id, qr_id)
    await session.delete(row)
    events.record(session, access.garden.id, access.actor, "qr.deleted", qr_id=qr_id)
    await session.commit()


async def resolve(session: AsyncSession, user: User, token: str) -> Resolved:
    """What a scanned code points at. Non-members get the same answer as for a missing code."""
    row = await session.scalar(select(QrCodeRow).where(QrCodeRow.token == token))
    garden = await session.get(GardenRow, row.garden_id) if row else None
    if row is None or garden is None or garden.deleted_at is not None:
        raise NotFound(NO_ACCESS)
    if not user.is_global_admin:
        member = await session.get(GardenMemberRow, (garden.id, user.sub))
        if member is None or not role_allows(member.role, GardenPermission.VIEW):
            raise NotFound(NO_ACCESS)
    return Resolved(target_type=row.target_type, garden_id=garden.id, plant_id=row.plant_id)


async def _get(session: AsyncSession, garden_id: int, qr_id: int) -> QrCodeRow:
    row = await session.scalar(select(QrCodeRow).where(QrCodeRow.id == qr_id, QrCodeRow.garden_id == garden_id))
    if row is None:
        raise NotFound("QR code not found.")
    return row
