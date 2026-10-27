"""FastAPI dependencies shared by routers: the caller's account and their access to a garden."""
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.access import GardenAccess
from app.auth import User, get_current_user
from app.db import get_session
from app.errors import Forbidden
from app.models import UserRow
from app.roles import GardenPermission
from app.services import access, users


async def current_account(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)) -> UserRow:
    return await users.ensure_user(session, user)


async def require_onboarded(account: UserRow = Depends(current_account)) -> UserRow:
    if not users.is_onboarded(account):
        raise Forbidden("Finish your profile (handle and display name) first.")
    return account


def require_global_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_global_admin:
        raise Forbidden("Global admin only.")
    return user


def require_garden(permission: GardenPermission, *, allow_deleted: bool = False):
    """Resolves the `garden_id` path parameter to a GardenAccess the caller holds `permission` on."""

    async def resolve(
        garden_id: int, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
    ) -> GardenAccess:
        return await access.resolve(session, garden_id, user, permission, allow_deleted=allow_deleted)

    return resolve
