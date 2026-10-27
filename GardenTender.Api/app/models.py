from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PlantRow(Base):
    __tablename__ = "plants"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String, index=True)  # Auth0 `sub`
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
