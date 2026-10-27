"""Who is acting on a garden, and through what: membership or the global admin override."""
from dataclasses import dataclass

from app.auth import User
from app.models import GardenRow
from app.roles import GardenRole


@dataclass(frozen=True)
class Actor:
    sub: str
    via_global_admin: bool = False


@dataclass(frozen=True)
class GardenAccess:
    garden: GardenRow
    user: User
    role: GardenRole | None  # None when the caller is not a member (global admin override)
    via_global_admin: bool

    @property
    def actor(self) -> Actor:
        return Actor(self.user.sub, self.via_global_admin)
