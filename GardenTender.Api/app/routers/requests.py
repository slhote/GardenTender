from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.access import GardenAccess
from app.db import get_session
from app.dependencies import require_garden
from app.roles import GardenPermission
from app.services import requests
from app.services.requests import RequestOut, RequestStatus

router = APIRouter(prefix="/gardens/{garden_id}/requests", tags=["requests"])


class RequestIn(BaseModel):
    type: str
    payload: dict
    note: str | None = None


class RequestPatch(BaseModel):
    payload: dict | None = None
    note: str | None = None


class DecisionIn(BaseModel):
    reason: str | None = None


@router.post("", response_model=RequestOut, status_code=status.HTTP_201_CREATED)
async def submit(
    body: RequestIn,
    access: GardenAccess = Depends(require_garden(GardenPermission.FILE_REQUESTS)),
    session: AsyncSession = Depends(get_session),
):
    return await requests.submit(session, access.garden.id, access.actor, access.role, body.type, body.payload, body.note)


@router.get("", response_model=list[RequestOut])
async def list_requests(
    status: RequestStatus | None = None,
    access: GardenAccess = Depends(require_garden(GardenPermission.VIEW)),
    session: AsyncSession = Depends(get_session),
):
    return await requests.list_requests(session, access, status)


@router.get("/{request_id}", response_model=RequestOut)
async def get_request(
    request_id: int,
    access: GardenAccess = Depends(require_garden(GardenPermission.VIEW)),
    session: AsyncSession = Depends(get_session),
):
    return await requests.get_visible(session, access, request_id)


@router.patch("/{request_id}", response_model=RequestOut)
async def edit_request(
    request_id: int,
    body: RequestPatch,
    access: GardenAccess = Depends(require_garden(GardenPermission.DECIDE_REQUESTS)),
    session: AsyncSession = Depends(get_session),
):
    return await requests.edit(session, access, request_id, body.payload, body.note)


@router.post("/{request_id}/approve", response_model=RequestOut)
async def approve(
    request_id: int,
    body: DecisionIn,
    access: GardenAccess = Depends(require_garden(GardenPermission.DECIDE_REQUESTS)),
    session: AsyncSession = Depends(get_session),
):
    return await requests.approve(session, access, request_id, body.reason)


@router.post("/{request_id}/reject", response_model=RequestOut)
async def reject(
    request_id: int,
    body: DecisionIn,
    access: GardenAccess = Depends(require_garden(GardenPermission.DECIDE_REQUESTS)),
    session: AsyncSession = Depends(get_session),
):
    return await requests.reject(session, access, request_id, body.reason)


@router.post("/{request_id}/cancel", response_model=RequestOut)
async def cancel(
    request_id: int,
    access: GardenAccess = Depends(require_garden(GardenPermission.FILE_REQUESTS)),
    session: AsyncSession = Depends(get_session),
):
    return await requests.cancel(session, access, request_id)
