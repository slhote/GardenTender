from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.access import GardenAccess
from app.auth import User, get_current_user
from app.db import get_session
from app.dependencies import get_links, require_garden
from app.roles import GardenPermission
from app.services import qr_codes
from app.services.notifier import Links

router = APIRouter(tags=["qr codes"])

_admin = require_garden(GardenPermission.QR_MANAGE)


@router.post("/gardens/{garden_id}/qr-codes", response_model=qr_codes.QrCodeResponse, status_code=status.HTTP_201_CREATED)
async def create_code(
    body: qr_codes.QrCodeRequest,
    access: GardenAccess = Depends(_admin),
    session: AsyncSession = Depends(get_session),
    links: Links = Depends(get_links),
):
    return await qr_codes.create(session, access, body, links)


@router.get("/gardens/{garden_id}/qr-codes", response_model=list[qr_codes.QrCodeResponse])
async def list_codes(access: GardenAccess = Depends(_admin), session: AsyncSession = Depends(get_session), links: Links = Depends(get_links)):
    return await qr_codes.list_codes(session, access.garden.id, links)


@router.patch("/gardens/{garden_id}/qr-codes/{qr_id}", response_model=qr_codes.QrCodeResponse)
async def update_code(
    qr_id: int,
    patch: qr_codes.UpdateQrCodeRequest,
    access: GardenAccess = Depends(_admin),
    session: AsyncSession = Depends(get_session),
    links: Links = Depends(get_links),
):
    return await qr_codes.update(session, access, qr_id, patch, links)


@router.delete("/gardens/{garden_id}/qr-codes/{qr_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_code(qr_id: int, access: GardenAccess = Depends(_admin), session: AsyncSession = Depends(get_session)):
    await qr_codes.delete(session, access, qr_id)


# Any signed-in user may scan; only members (or global admins) learn what the code points at.
@router.get("/qr/{token}", response_model=qr_codes.QrResolveResponse)
async def resolve(token: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    return await qr_codes.resolve(session, user, token)
