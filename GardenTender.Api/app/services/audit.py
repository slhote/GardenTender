"""Global admin audit log: one row per request made with a system:admin token (see app.audit)."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AdminAuditRow

REDACTED = "[redacted]"
_SECRET_KEY_PARTS = ("token", "secret", "password")


class AuditEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_sub: str
    method: str
    path: str
    path_params: dict
    body: dict | list | str | None
    status_code: int
    garden_id: int | None
    created_at: datetime


def redact(value):
    """Replaces values under secret-looking keys (invite tokens etc.) at any depth."""
    if isinstance(value, dict):
        return {k: REDACTED if any(p in k.lower() for p in _SECRET_KEY_PARTS) else redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


async def record(session: AsyncSession, entry: AdminAuditRow) -> None:
    session.add(entry)
    await session.commit()


async def list_entries(session: AsyncSession, limit: int, before_id: int | None) -> list[AuditEntryResponse]:
    query = select(AdminAuditRow).order_by(AdminAuditRow.id.desc()).limit(limit)
    if before_id is not None:
        query = query.where(AdminAuditRow.id < before_id)
    return [AuditEntryResponse.model_validate(r) for r in await session.scalars(query)]
