"""ASGI middleware that writes every global admin request to the admin audit log.

It sits outside routing, so no endpoint has to remember to log: whatever a `system:admin` token touches, reads
included, is recorded with its outcome. The caller comes from `request.state.user` (set by get_current_user).
"""
import json
import logging
from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.models import AdminAuditRow
from app.services import audit

log = logging.getLogger(__name__)
MAX_BODY_BYTES = 16_384


class AuditMiddleware:
    def __init__(self, app: ASGIApp, get_sessionmaker: Callable[[], async_sessionmaker[AsyncSession]]):
        self.app = app
        self.get_sessionmaker = get_sessionmaker

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        body = bytearray()
        status_code = 500  # if the app raises before responding

        async def receive_and_capture() -> Message:
            message = await receive()
            if message["type"] == "http.request" and len(body) < MAX_BODY_BYTES:
                body.extend(message.get("body", b"")[: MAX_BODY_BYTES - len(body)])
            return message

        async def send_and_capture(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive_and_capture, send_and_capture)
        finally:
            user = scope.get("state", {}).get("user")
            if user is not None and user.is_global_admin:
                await self._write(scope, user.sub, bytes(body), status_code)

    async def _write(self, scope: Scope, actor_sub: str, body: bytes, status_code: int) -> None:
        path_params = {k: str(v) for k, v in scope.get("path_params", {}).items()}
        garden_id = path_params.get("garden_id")
        entry = AdminAuditRow(
            actor_sub=actor_sub,
            method=scope["method"],
            path=scope["path"],
            path_params=path_params,
            body=_parse_body(body),
            status_code=status_code,
            garden_id=int(garden_id) if garden_id and garden_id.isdigit() else None,
        )
        try:
            async with self.get_sessionmaker()() as session:
                await audit.record(session, entry)
        except Exception:
            # The response is already sent; losing an audit row must be loud, not silent.
            log.exception("Failed to write admin audit log entry for %s %s by %s", scope["method"], scope["path"], actor_sub)


def _parse_body(body: bytes):
    if not body:
        return None
    try:
        return audit.redact(json.loads(body))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return f"<{len(body)} bytes, not JSON>"
