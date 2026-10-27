from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _now() -> datetime:
    return datetime.now(UTC)


class PlantRow(Base):
    __tablename__ = "plants"

    id: Mapped[int] = mapped_column(primary_key=True)
    garden_id: Mapped[int] = mapped_column(ForeignKey("gardens.id", ondelete="CASCADE"), index=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.sub", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String)
    species: Mapped[str] = mapped_column(String, default="")
    notes: Mapped[str] = mapped_column(String, default="")
    water_every_days: Mapped[int] = mapped_column(Integer, default=7)


class UserRow(Base):
    __tablename__ = "users"

    sub: Mapped[str] = mapped_column(String, primary_key=True)  # Auth0 `sub`
    # Stored lowercase, so the unique index makes handles case-insensitively unique. Null until onboarding.
    handle: Mapped[str | None] = mapped_column(String, unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String)
    email: Mapped[str | None] = mapped_column(String)  # from the token; never shown to other users
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class GardenRow(Base):
    __tablename__ = "gardens"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.sub"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)  # soft delete


class GardenMemberRow(Base):
    __tablename__ = "garden_members"

    garden_id: Mapped[int] = mapped_column(ForeignKey("gardens.id", ondelete="CASCADE"), primary_key=True)
    user_sub: Mapped[str] = mapped_column(ForeignKey("users.sub", ondelete="CASCADE"), primary_key=True, index=True)
    role: Mapped[str] = mapped_column(String)  # app.roles.GardenRole
    invited_by: Mapped[str | None] = mapped_column(ForeignKey("users.sub", ondelete="SET NULL"))
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class GardenEventRow(Base):
    """Append-only garden history, written in the same transaction as the action it records."""

    __tablename__ = "garden_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    garden_id: Mapped[int] = mapped_column(ForeignKey("gardens.id", ondelete="CASCADE"), index=True)
    actor_sub: Mapped[str] = mapped_column(String)
    via_global_admin: Mapped[bool] = mapped_column(Boolean, default=False)  # acted through the system:admin override
    type: Mapped[str] = mapped_column(String)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AdminAuditRow(Base):
    """Every request made with a system:admin token, written by app.audit.AuditMiddleware."""

    __tablename__ = "admin_audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_sub: Mapped[str] = mapped_column(String, index=True)
    method: Mapped[str] = mapped_column(String)
    path: Mapped[str] = mapped_column(String)
    path_params: Mapped[dict] = mapped_column(JSON, default=dict)
    body: Mapped[dict | list | str | None] = mapped_column(JSON)  # redacted
    status_code: Mapped[int] = mapped_column(Integer)
    garden_id: Mapped[int | None] = mapped_column(Integer, index=True)  # no FK: the log outlives purged gardens
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class GardenRequestRow(Base):
    """Something a member asked for that an admin must approve. The real row is only created on approval."""

    __tablename__ = "garden_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    garden_id: Mapped[int] = mapped_column(ForeignKey("gardens.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String)  # app.services.requests.KINDS key
    payload: Mapped[dict] = mapped_column(JSON)
    note: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, index=True)  # app.services.requests.RequestStatus
    requested_by: Mapped[str] = mapped_column(ForeignKey("users.sub", ondelete="CASCADE"))
    decided_by: Mapped[str | None] = mapped_column(ForeignKey("users.sub", ondelete="SET NULL"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_reason: Mapped[str | None] = mapped_column(String)
    result: Mapped[dict | None] = mapped_column(JSON)  # what approval produced, e.g. {"plant_id": 3}
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class InviteRow(Base):
    """A single-use invite. Only the token's hash is stored; the token itself lives in the link."""

    __tablename__ = "invites"

    id: Mapped[int] = mapped_column(primary_key=True)
    garden_id: Mapped[int] = mapped_column(ForeignKey("gardens.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String, unique=True)
    via: Mapped[str] = mapped_column(String)  # app.services.invites.InviteVia
    role: Mapped[str] = mapped_column(String)
    invited_by: Mapped[str | None] = mapped_column(ForeignKey("users.sub", ondelete="SET NULL"))
    invitee_sub: Mapped[str | None] = mapped_column(ForeignKey("users.sub", ondelete="CASCADE"), index=True)
    email: Mapped[str | None] = mapped_column(String)  # the address the inviter typed, if any
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_by: Mapped[str | None] = mapped_column(ForeignKey("users.sub", ondelete="SET NULL"))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    declined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class QrCodeRow(Base):
    """A printable, retargetable code. It encodes only `/q/<token>`; the target is resolved by the API."""

    __tablename__ = "qr_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(String, unique=True)
    garden_id: Mapped[int] = mapped_column(ForeignKey("gardens.id", ondelete="CASCADE"), index=True)
    target_type: Mapped[str] = mapped_column(String)  # app.services.qr_codes.QrTarget
    # One nullable foreign key per target type, so a code is deleted with its target.
    plant_id: Mapped[int | None] = mapped_column(ForeignKey("plants.id", ondelete="CASCADE"), index=True)
    label: Mapped[str | None] = mapped_column(String)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.sub", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
