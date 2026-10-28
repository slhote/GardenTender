"""Development-only endpoints, mounted by `create_app` only when DEBUG_ENDPOINTS is on.

Example: `/debug/whoami` shows what the API read from your access token, which helps check Auth0 setup
(the `system:admin` permission, the email claim) without reading JWTs by hand.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth import User, get_current_user

# Read by tests/test_routers.py: this router is deliberately not in the default router list.
NOT_MOUNTED = "Debug-only: mounted by create_app() when DEBUG_ENDPOINTS is on."

router = APIRouter(prefix="/debug", tags=["debug"])


class WhoAmIResponse(BaseModel):
    sub: str
    email: str | None  # the caller's own token claim
    permissions: list[str]
    is_global_admin: bool


@router.get("/whoami", response_model=WhoAmIResponse)
async def whoami(user: User = Depends(get_current_user)):
    return WhoAmIResponse(
        sub=user.sub, email=user.email, permissions=sorted(user.permissions), is_global_admin=user.is_global_admin
    )
