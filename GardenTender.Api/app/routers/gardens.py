from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.access import Actor, GardenAccess
from app.config import Settings, get_settings
from app.db import get_session
from app.dependencies import require_garden, require_onboarded
from app.models import UserRow
from app.roles import GardenPermission, GardenRole
from app.services import gardens

router = APIRouter(prefix="/gardens", tags=["gardens"])


class GardenIn(BaseModel):
    name: str


class NewMemberIn(BaseModel):
    handle: str
    role: GardenRole = GardenRole.CONTRIBUTOR


class RoleIn(BaseModel):
    role: GardenRole


@router.post("", response_model=gardens.GardenOut, status_code=status.HTTP_201_CREATED)
async def create_garden(body: GardenIn, account: UserRow = Depends(require_onboarded), session: AsyncSession = Depends(get_session)):
    return await gardens.create(session, Actor(account.sub), body.name)


@router.get("", response_model=list[gardens.GardenOut])
async def my_gardens(account: UserRow = Depends(require_onboarded), session: AsyncSession = Depends(get_session)):
    return await gardens.list_mine(session, account.sub)


@router.get("/{garden_id}", response_model=gardens.GardenOut)
async def get_garden(access: GardenAccess = Depends(require_garden(GardenPermission.VIEW))):
    return gardens.to_out(access)


@router.patch("/{garden_id}", response_model=gardens.GardenOut)
async def rename_garden(
    body: GardenIn,
    access: GardenAccess = Depends(require_garden(GardenPermission.MANAGE)),
    session: AsyncSession = Depends(get_session),
):
    return await gardens.rename(session, access, body.name)


@router.delete("/{garden_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_garden(
    access: GardenAccess = Depends(require_garden(GardenPermission.MANAGE)), session: AsyncSession = Depends(get_session)
):
    await gardens.soft_delete(session, access)


@router.post("/{garden_id}/restore", response_model=gardens.GardenOut)
async def restore_garden(
    access: GardenAccess = Depends(require_garden(GardenPermission.MANAGE, allow_deleted=True)),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    return await gardens.restore(session, access, settings.garden_retention_days)


@router.get("/{garden_id}/members", response_model=list[gardens.MemberOut])
async def list_members(
    access: GardenAccess = Depends(require_garden(GardenPermission.VIEW)), session: AsyncSession = Depends(get_session)
):
    return await gardens.list_members(session, access.garden.id)


@router.post("/{garden_id}/members", response_model=gardens.MemberOut, status_code=status.HTTP_201_CREATED)
async def add_member(
    body: NewMemberIn,
    access: GardenAccess = Depends(require_garden(GardenPermission.ADD_MEMBER_DIRECTLY)),
    session: AsyncSession = Depends(get_session),
):
    return await gardens.add_member(session, access, body.handle, body.role)


@router.patch("/{garden_id}/members/{handle}", response_model=gardens.MemberOut)
async def change_role(
    handle: str,
    body: RoleIn,
    access: GardenAccess = Depends(require_garden(GardenPermission.MANAGE_MEMBERS)),
    session: AsyncSession = Depends(get_session),
):
    return await gardens.change_role(session, access, handle, body.role)


@router.delete("/{garden_id}/members/{handle}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    handle: str,
    access: GardenAccess = Depends(require_garden(GardenPermission.VIEW)),  # leaving needs only membership
    session: AsyncSession = Depends(get_session),
):
    await gardens.remove_member(session, access, handle)
