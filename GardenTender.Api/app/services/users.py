"""User accounts: the local directory row behind an Auth0 `sub`, and onboarding (handle + display name)."""
import re

from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import User
from app.errors import Conflict, InvalidInput
from app.models import UserRow

HANDLE_RE = re.compile(r"[a-z0-9_]{3,20}")
DISPLAY_NAME_MAX = 50


class Me(BaseModel):
    handle: str | None
    display_name: str | None
    email: str | None  # the caller's own email only
    onboarded: bool


def to_me(row: UserRow) -> Me:
    return Me(
        handle=row.handle,
        display_name=row.display_name,
        email=row.email,
        onboarded=row.handle is not None and row.display_name is not None,
    )


async def ensure_user(session: AsyncSession, user: User) -> UserRow:
    """Creates the caller's row on first sight and keeps the email in sync with the token."""
    row = await session.get(UserRow, user.sub)
    if row is None:
        row = UserRow(sub=user.sub, email=user.email)
        session.add(row)
        try:
            await session.commit()
        except IntegrityError:  # a concurrent first request created it
            await session.rollback()
            row = await session.get(UserRow, user.sub)
    elif user.email is not None and row.email != user.email:
        row.email = user.email
        await session.commit()
    return row


def normalize_handle(handle: str) -> str:
    """Accepts any casing; handles are validated and stored lowercase."""
    h = handle.strip().lstrip("@").lower()
    if not HANDLE_RE.fullmatch(h):
        raise InvalidInput("Handle must be 3-20 characters: letters, digits or underscore.")
    return h


def normalize_display_name(name: str) -> str:
    n = " ".join(name.split())
    if not 1 <= len(n) <= DISPLAY_NAME_MAX:
        raise InvalidInput(f"Display name must be 1-{DISPLAY_NAME_MAX} characters.")
    return n


async def set_profile(session: AsyncSession, user: User, handle: str | None, display_name: str | None) -> Me:
    """Sets the display name, and the handle once (handles are immutable after onboarding)."""
    row = await ensure_user(session, user)
    if handle is not None:
        h = normalize_handle(handle)
        if row.handle is not None and row.handle != h:
            raise InvalidInput("Handle can't be changed.")
        row.handle = h
    if display_name is not None:
        row.display_name = normalize_display_name(display_name)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise Conflict("That handle is taken.")
    return to_me(row)
