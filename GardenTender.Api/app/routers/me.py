from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import User, get_current_user
from app.db import get_session
from app.services import users

router = APIRouter(prefix="/me", tags=["me"])


class UpdateProfileRequest(BaseModel):
    handle: str | None = None
    display_name: str | None = None


@router.get("", response_model=users.MeResponse)
async def get_me(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    return users.to_me(await users.ensure_user(session, user))


@router.patch("", response_model=users.MeResponse)
async def patch_me(patch: UpdateProfileRequest, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    return await users.set_profile(session, user, patch.handle, patch.display_name)
