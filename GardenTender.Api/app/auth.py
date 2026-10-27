from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings
from app.roles import SYSTEM_ADMIN

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class User:
    sub: str
    permissions: frozenset[str]
    email: str | None = None  # added to the access token by an Auth0 Action

    @property
    def is_global_admin(self) -> bool:
        return SYSTEM_ADMIN in self.permissions


@lru_cache
def _jwks_client() -> jwt.PyJWKClient:
    return jwt.PyJWKClient(f"https://{get_settings().auth0_domain}/.well-known/jwks.json")


def authenticate(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> User:
    """Verifies the Auth0 access token (signature, issuer, audience, expiry)."""
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    settings = get_settings()
    try:
        key = _jwks_client().get_signing_key_from_jwt(creds.credentials).key
        claims = jwt.decode(
            creds.credentials,
            key,
            algorithms=["RS256"],
            audience=settings.auth0_audience,
            issuer=f"https://{settings.auth0_domain}/",
        )
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    return User(
        sub=claims["sub"],
        permissions=frozenset(claims.get("permissions", [])),
        email=claims.get(f"{settings.auth0_claims_namespace}email"),
    )


def get_current_user(request: Request, user: User = Depends(authenticate)) -> User:
    """The authenticated caller. Also exposed on `request.state.user` for middleware (admin audit log)."""
    request.state.user = user
    return user


def require_permission(permission: str):
    def check(user: User = Depends(get_current_user)) -> User:
        if permission not in user.permissions:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Missing permission: {permission}")
        return user

    return check
