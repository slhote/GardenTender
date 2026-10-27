from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import User, get_current_user
from app.db import get_session
from app.dependencies import current_account
from app.errors import Forbidden
from app.models import UserRow
from app.services import users

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/search", response_model=list[users.PublicUser])
async def search_users(
    q: str = Query(..., description="Prefix of a handle or display name"),
    user: User = Depends(get_current_user),
    account: UserRow = Depends(current_account),
    session: AsyncSession = Depends(get_session),
):
    # Only garden members need to find people (to invite them); nobody can ask to join a garden.
    if not user.is_global_admin and not await users.is_member_anywhere(session, account.sub):
        raise Forbidden("Join or create a garden to search for users.")
    return await users.search(session, q)
