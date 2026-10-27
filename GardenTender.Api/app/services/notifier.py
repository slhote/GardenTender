"""Side effects that must only happen once the database transaction has committed (emails today).

Services queue messages while they work; the caller commits, then flushes. A failed commit never sends an
email with a dead invite link, and a failed send never rolls back committed work (it is logged instead).
"""
import logging
from dataclasses import dataclass, field

from app.services.email import EmailMessage, EmailSender

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Links:
    """Public URLs (App Links on the Android side). Built from PUBLIC_BASE_URL at render time, never stored."""

    base_url: str

    def invite(self, token: str) -> str:
        return f"{self.base_url.rstrip('/')}/i/{token}"

    def qr(self, token: str) -> str:
        return f"{self.base_url.rstrip('/')}/q/{token}"


@dataclass
class Notifier:
    email: EmailSender
    links: Links
    _queued: list[EmailMessage] = field(default_factory=list)

    def queue_email(self, to: str, subject: str, body: str) -> None:
        self._queued.append(EmailMessage(to, subject, body))

    async def flush(self) -> None:
        queued, self._queued = self._queued, []
        for message in queued:
            try:
                await self.email.send(message)
            except Exception:
                log.exception("Failed to send email %r to %s", message.subject, message.to)
