"""Outgoing email behind a small interface, so the provider (not chosen yet) is a config change."""
import logging
from dataclasses import dataclass
from typing import Protocol

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    body: str


class EmailSender(Protocol):
    async def send(self, message: EmailMessage) -> None: ...


class ConsoleEmailSender:
    """Dev/test sender: writes the email to the log instead of delivering it."""

    async def send(self, message: EmailMessage) -> None:
        log.info("Email to %s: %s\n%s", message.to, message.subject, message.body)
