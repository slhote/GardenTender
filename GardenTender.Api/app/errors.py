"""Domain errors raised by services. app/exception_handlers.py is the one place they become HTTP responses.

Services raise these instead of HTTPException so they stay usable outside HTTP (LLM tools, jobs).
"""


class DomainError(Exception):
    pass


class InvalidInput(DomainError):
    pass


class NotFound(DomainError):
    pass


class Conflict(DomainError):
    pass
