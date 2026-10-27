from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.errors import Conflict, DomainError, InvalidInput, NotFound
from app.llm.base import LlmUnavailable

_STATUS: dict[type[DomainError], int] = {InvalidInput: 400, NotFound: 404, Conflict: 409}


def _status_for(exc: DomainError) -> int:
    return next((code for cls, code in _STATUS.items() if isinstance(exc, cls)), 400)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def domain_error(_: Request, exc: DomainError):
        return JSONResponse({"detail": str(exc)}, status_code=_status_for(exc))

    @app.exception_handler(LlmUnavailable)
    async def llm_unavailable(_: Request, exc: LlmUnavailable):
        return JSONResponse({"detail": "The chat model is unavailable."}, status_code=502)
