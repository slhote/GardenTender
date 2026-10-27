"""Global admin views. Garden CRUD for global admins goes through the normal /gardens routes (override)."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.dependencies import require_global_admin
from app.services import audit, gardens

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_global_admin)])


@router.get("/gardens", response_model=list[gardens.GardenOut])
async def all_gardens(include_deleted: bool = False, session: AsyncSession = Depends(get_session)):
    return await gardens.list_all(session, include_deleted)


@router.get("/audit-log", response_model=list[audit.AuditEntry])
async def audit_log(
    limit: int = Query(50, ge=1, le=200),
    before_id: int | None = Query(None, description="Page backwards from this entry id"),
    session: AsyncSession = Depends(get_session),
):
    return await audit.list_entries(session, limit, before_id)
