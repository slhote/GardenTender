from datetime import timedelta

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.access import GardenAccess
from app.config import Settings, get_settings
from app.db import get_session
from app.dependencies import current_account, get_notifier, require_garden
from app.models import UserRow
from app.roles import GardenPermission, GardenRole
from app.services import invites
from app.services.notifier import Notifier

router = APIRouter(tags=["invites"])


class QrInviteIn(BaseModel):
    role: GardenRole = GardenRole.CONTRIBUTOR


class AcceptIn(BaseModel):
    token: str


class Joined(BaseModel):
    garden_id: int


# Garden admins. Contributors ask for invites through a request of type "invite_user".
@router.post("/gardens/{garden_id}/invites", response_model=invites.InviteOut, status_code=status.HTTP_201_CREATED)
async def invite(
    body: invites.InviteTarget,
    access: GardenAccess = Depends(require_garden(GardenPermission.INVITE)),
    session: AsyncSession = Depends(get_session),
    notifier: Notifier = Depends(get_notifier),
    settings: Settings = Depends(get_settings),
):
    out = await invites.create(session, access.garden, access.actor, body, notifier, timedelta(days=settings.invite_ttl_days))
    await session.commit()
    await notifier.flush()
    return out


@router.post("/gardens/{garden_id}/invites/qr", response_model=invites.CreatedQrInvite, status_code=status.HTTP_201_CREATED)
async def qr_invite(
    body: QrInviteIn,
    access: GardenAccess = Depends(require_garden(GardenPermission.INVITE)),
    session: AsyncSession = Depends(get_session),
    notifier: Notifier = Depends(get_notifier),
    settings: Settings = Depends(get_settings),
):
    return await invites.create_qr(session, access, body.role, notifier, timedelta(minutes=settings.qr_invite_ttl_minutes))


@router.get("/gardens/{garden_id}/invites", response_model=list[invites.InviteOut])
async def pending_invites(
    access: GardenAccess = Depends(require_garden(GardenPermission.INVITE)), session: AsyncSession = Depends(get_session)
):
    return await invites.list_pending(session, access.garden.id)


@router.delete("/gardens/{garden_id}/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_invite(
    invite_id: int,
    access: GardenAccess = Depends(require_garden(GardenPermission.INVITE)),
    session: AsyncSession = Depends(get_session),
):
    await invites.revoke(session, access, invite_id)


# Invitees.
@router.post("/invites/accept", response_model=Joined)
async def accept_link(body: AcceptIn, account: UserRow = Depends(current_account), session: AsyncSession = Depends(get_session)):
    return Joined(garden_id=await invites.accept_token(session, account, body.token))


@router.get("/me/invites", response_model=list[invites.MyInvite])
async def my_invites(account: UserRow = Depends(current_account), session: AsyncSession = Depends(get_session)):
    return await invites.mine(session, account.sub)


@router.post("/me/invites/{invite_id}/accept", response_model=Joined)
async def accept_mine(invite_id: int, account: UserRow = Depends(current_account), session: AsyncSession = Depends(get_session)):
    return Joined(garden_id=await invites.accept_mine(session, account, invite_id))


@router.post("/me/invites/{invite_id}/decline", status_code=status.HTTP_204_NO_CONTENT)
async def decline_mine(invite_id: int, account: UserRow = Depends(current_account), session: AsyncSession = Depends(get_session)):
    await invites.decline_mine(session, account, invite_id)
