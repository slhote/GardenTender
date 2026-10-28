"""User accounts: the local directory row behind an Auth0 `sub`, and onboarding (handle + display name)."""
import re

from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import User
from app.errors import Conflict, InvalidInput
from app.models import GardenMemberRow, UserRow
from app.services.text import normalize_name

HANDLE_RE = re.compile(r"[a-z0-9_]{3,20}")
DISPLAY_NAME_MAX = 50


SEARCH_MIN_CHARS = 2
SEARCH_LIMIT = 20


class PublicUserResponse(BaseModel):
    """What other users may see about someone. Never includes email."""

    handle: str
    display_name: str


class MeResponse(BaseModel):
    handle: str | None
    display_name: str | None
    email: str | None  # the caller's own email only
    onboarded: bool


def is_onboarded(row: UserRow) -> bool:
    return row.handle is not None and row.display_name is not None


def to_me(row: UserRow) -> MeResponse:
    return MeResponse(
        handle=row.handle,
        display_name=row.display_name,
        email=row.email,
        onboarded=is_onboarded(row),
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
    return normalize_name(name, "Display name", DISPLAY_NAME_MAX)


async def set_profile(session: AsyncSession, user: User, handle: str | None, display_name: str | None) -> MeResponse:
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


async def get_by_handle(session: AsyncSession, handle: str) -> UserRow | None:
    return await session.scalar(select(UserRow).where(UserRow.handle == handle.strip().lstrip("@").lower()))


async def is_member_anywhere(session: AsyncSession, sub: str) -> bool:
    return await session.scalar(select(GardenMemberRow.user_sub).where(GardenMemberRow.user_sub == sub).limit(1)) is not None


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def search(session: AsyncSession, query: str) -> list[PublicUserResponse]:
    """Prefix match on handle or display name; only onboarded users."""
    q = query.strip().lstrip("@")
    if len(q) < SEARCH_MIN_CHARS:
        raise InvalidInput(f"Search needs at least {SEARCH_MIN_CHARS} characters.")
    pattern = _escape_like(q.lower()) + "%"
    rows = await session.scalars(
        select(UserRow)
        .where(
            UserRow.handle.is_not(None),
            UserRow.display_name.is_not(None),
            or_(UserRow.handle.like(pattern, escape="\\"), UserRow.display_name.ilike(pattern, escape="\\")),
        )
        .order_by(UserRow.handle)
        .limit(SEARCH_LIMIT)
    )
    return [PublicUserResponse(handle=r.handle, display_name=r.display_name) for r in rows]
