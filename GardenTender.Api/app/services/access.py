"""Resolves what a caller may do in a garden: their membership role, else the global admin override."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.access import GardenAccess
from app.auth import User
from app.errors import Forbidden, NotFound
from app.models import GardenMemberRow, GardenRow
from app.roles import GardenPermission, GardenRole, role_allows


async def resolve(
    session: AsyncSession, garden_id: int, user: User, permission: GardenPermission, *, allow_deleted: bool = False
) -> GardenAccess:
    garden = await session.get(GardenRow, garden_id)
    member = await session.get(GardenMemberRow, (garden_id, user.sub)) if garden else None
    if garden is None or (garden.deleted_at is not None and not allow_deleted):
        raise NotFound("Garden not found.")
    if member is not None and role_allows(member.role, permission):
        return GardenAccess(garden, user, GardenRole(member.role), via_global_admin=False)
    if user.is_global_admin:
        return GardenAccess(garden, user, GardenRole(member.role) if member else None, via_global_admin=True)
    if member is None:
        raise NotFound("Garden not found.")  # same answer as a missing garden: don't reveal it exists
    raise Forbidden("Your role in this garden doesn't allow that.")
