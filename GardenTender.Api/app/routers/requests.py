from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.access import GardenAccess
from app.db import get_session
from app.dependencies import get_request_deps, require_garden
from app.roles import GardenPermission
from app.services import requests
from app.services.requests import RequestDeps, ApprovalResponse, RequestStatus

router = APIRouter(prefix="/gardens/{garden_id}/requests", tags=["requests"])


class ApprovalSubmitRequest(BaseModel):
    type: str
    payload: dict
    note: str | None = None


class ApprovalUpdateRequest(BaseModel):
    payload: dict | None = None
    note: str | None = None


class ApprovalDecisionRequest(BaseModel):
    reason: str | None = None


@router.post("", response_model=ApprovalResponse, status_code=status.HTTP_201_CREATED)
async def submit(
    body: ApprovalSubmitRequest,
    access: GardenAccess = Depends(require_garden(GardenPermission.FILE_REQUESTS)),
    session: AsyncSession = Depends(get_session),
    deps: RequestDeps = Depends(get_request_deps),
):
    return await requests.submit(session, access.garden.id, access.actor, access.role, body.type, body.payload, body.note, deps)


@router.get("", response_model=list[ApprovalResponse])
async def list_requests(
    status: RequestStatus | None = None,
    access: GardenAccess = Depends(require_garden(GardenPermission.VIEW)),
    session: AsyncSession = Depends(get_session),
):
    return await requests.list_requests(session, access, status)


@router.get("/{request_id}", response_model=ApprovalResponse)
async def get_request(
    request_id: int,
    access: GardenAccess = Depends(require_garden(GardenPermission.VIEW)),
    session: AsyncSession = Depends(get_session),
):
    return await requests.get_visible(session, access, request_id)


@router.patch("/{request_id}", response_model=ApprovalResponse)
async def edit_request(
    request_id: int,
    body: ApprovalUpdateRequest,
    access: GardenAccess = Depends(require_garden(GardenPermission.DECIDE_REQUESTS)),
    session: AsyncSession = Depends(get_session),
):
    return await requests.edit(session, access, request_id, body.payload, body.note)


@router.post("/{request_id}/approve", response_model=ApprovalResponse)
async def approve(
    request_id: int,
    body: ApprovalDecisionRequest,
    access: GardenAccess = Depends(require_garden(GardenPermission.DECIDE_REQUESTS)),
    session: AsyncSession = Depends(get_session),
    deps: RequestDeps = Depends(get_request_deps),
):
    return await requests.approve(session, access, request_id, body.reason, deps)


@router.post("/{request_id}/reject", response_model=ApprovalResponse)
async def reject(
    request_id: int,
    body: ApprovalDecisionRequest,
    access: GardenAccess = Depends(require_garden(GardenPermission.DECIDE_REQUESTS)),
    session: AsyncSession = Depends(get_session),
):
    return await requests.reject(session, access, request_id, body.reason)


@router.post("/{request_id}/cancel", response_model=ApprovalResponse)
async def cancel(
    request_id: int,
    access: GardenAccess = Depends(require_garden(GardenPermission.FILE_REQUESTS)),
    session: AsyncSession = Depends(get_session),
):
    return await requests.cancel(session, access, request_id)
