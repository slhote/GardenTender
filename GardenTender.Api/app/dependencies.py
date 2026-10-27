"""FastAPI dependencies shared by routers: the caller's account and their access to a garden."""
from datetime import timedelta

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.access import GardenAccess
from app.auth import User, get_current_user
from app.config import Settings, get_settings
from app.db import get_session
from app.errors import Forbidden
from app.models import UserRow
from app.roles import GardenPermission
from app.services import access, users
from app.services.email import ConsoleEmailSender, EmailSender
from app.services.notifier import Links, Notifier
from app.services.requests import RequestDeps


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


def require_garden(permission: GardenPermission, *, allow_deleted: bool = False, allow_override: bool = True):
    """Resolves the `garden_id` path parameter to a GardenAccess the caller holds `permission` on.

    `allow_override=False` requires real membership (the global admin override doesn't apply).
    """

    async def resolve(
        garden_id: int,
        user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_session),
        _: UserRow = Depends(current_account),  # actions record the caller (created_by etc.), so their row must exist
    ) -> GardenAccess:
        return await access.resolve(
            session, garden_id, user, permission, allow_deleted=allow_deleted, allow_override=allow_override
        )

    return resolve


def get_email_sender(settings: Settings = Depends(get_settings)) -> EmailSender:
    if settings.email_backend == "console":
        return ConsoleEmailSender()
    raise RuntimeError(f"Unknown EMAIL_BACKEND {settings.email_backend!r}")


def get_links(settings: Settings = Depends(get_settings)) -> Links:
    return Links(settings.public_base_url)


def get_notifier(email: EmailSender = Depends(get_email_sender), links: Links = Depends(get_links)) -> Notifier:
    return Notifier(email, links)  # one per request: it queues emails until the request's transaction commits


def get_request_deps(notifier: Notifier = Depends(get_notifier), settings: Settings = Depends(get_settings)) -> RequestDeps:
    return RequestDeps(notifier, timedelta(days=settings.invite_ttl_days))
