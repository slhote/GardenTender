"""Garden roles and what each may do. Roles live in garden_members; this map is the only place they gain meaning.

The global admin (Auth0 permission `system:admin`) passes every garden permission check, including ones no
garden role grants (e.g. adding a member directly instead of through an invite).
"""
from enum import StrEnum

SYSTEM_ADMIN = "system:admin"


class GardenRole(StrEnum):
    ADMIN = "admin"
    CONTRIBUTOR = "contributor"


class GardenPermission(StrEnum):
    VIEW = "garden:view"
    MANAGE = "garden:manage"  # rename, delete, restore
    MANAGE_MEMBERS = "members:manage"  # change roles, remove others
    ADD_MEMBER_DIRECTLY = "members:add"  # global admin only; everyone else joins through invites


_CONTRIBUTOR = frozenset({GardenPermission.VIEW})
_ADMIN = _CONTRIBUTOR | {GardenPermission.MANAGE, GardenPermission.MANAGE_MEMBERS}

ROLE_PERMISSIONS: dict[GardenRole, frozenset[GardenPermission]] = {
    GardenRole.CONTRIBUTOR: _CONTRIBUTOR,
    GardenRole.ADMIN: _ADMIN,
}


def role_allows(role: GardenRole | str, permission: GardenPermission) -> bool:
    return permission in ROLE_PERMISSIONS.get(GardenRole(role), frozenset())
