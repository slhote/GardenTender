from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth import User, require_permission
from app.config import get_settings
from app.db import create_tables, dispose_engine, get_session, get_sessionmaker
from app.llm.base import LlmProvider, LlmUnavailable
from app.llm.ollama import OllamaProvider
from app.llm.claude import ClaudeProvider
from app.llm.loop import DeviceResult, run_chat
from app.services import plants

@asynccontextmanager
async def lifespan(_: FastAPI):
    # MVP: create tables on startup. Move to Alembic migrations before the schema changes.
    await create_tables()
    yield
    await dispose_engine()


app = FastAPI(title="GardenTender API", lifespan=lifespan)


@app.exception_handler(LlmUnavailable)
async def llm_unavailable(_, exc: LlmUnavailable):
    return JSONResponse({"detail": "The chat model is unavailable."}, status_code=502)


class DeviceResultIn(BaseModel):
    content: str
    is_error: bool = False


class ChatRequest(BaseModel):
    # Opaque history echoed back from the previous response; the new user text is appended server-side.
    history: list[dict] = []
    message: str | None = None
    decisions: dict[str, bool] = {}
    device_results: dict[str, DeviceResultIn] = {}
    timezone: str | None = None  # IANA name, e.g. America/Chicago
    model: str | None = None  # one of GET /models; only honored for the ollama provider


@app.get("/models")
async def list_models(_: User = Depends(require_permission("chat:use"))):
    s = get_settings()
    if s.llm_provider == "ollama":
        models = s.ollama_models if s.llm_model in s.ollama_models else [s.llm_model, *s.ollama_models]
        return {"models": models, "default": s.llm_model}
    return {"models": [s.llm_model], "default": s.llm_model}


def get_provider(req: ChatRequest) -> LlmProvider:
    s = get_settings()
    if s.llm_provider == "claude":
        return ClaudeProvider(s.anthropic_api_key, s.llm_model)
    if s.llm_provider == "ollama":
        model = req.model or s.llm_model
        if model != s.llm_model and model not in s.ollama_models:
            raise HTTPException(400, f"Unknown model {model!r}.")
        return OllamaProvider(s.ollama_base_url, model)
    raise HTTPException(500, f"Unknown LLM provider {s.llm_provider!r}")


class PendingOut(BaseModel):
    id: str
    name: str
    input: dict
    runs_on: str
    confirm: bool


class ChatResponse(BaseModel):
    history: list[dict]
    reply: str
    pending: list[PendingOut]


@app.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    user: User = Depends(require_permission("chat:use")),
    provider: LlmProvider = Depends(get_provider),
    maker: async_sessionmaker[AsyncSession] = Depends(get_sessionmaker),
):
    history = list(req.history)
    if req.message:
        history.append({"role": "user", "content": [{"type": "text", "text": req.message}]})
    result = await run_chat(
        maker,
        user,
        history,
        req.decisions,
        provider,
        get_settings().max_tool_steps,
        device_results={k: DeviceResult(v.content, v.is_error) for k, v in req.device_results.items()},
        tz_name=req.timezone,
    )
    return ChatResponse(
        history=result.history,
        reply=result.reply,
        pending=[PendingOut(id=p.id, name=p.name, input=p.input, runs_on=p.runs_on, confirm=p.confirm) for p in result.pending],
    )


# Direct endpoints call the same services as the LLM tools.
@app.get("/plants")
async def get_plants(
    user: User = Depends(require_permission("plants:read")), session: AsyncSession = Depends(get_session)
):
    return await plants.list_plants(session, user.sub)


class PlantPatch(BaseModel):
    field: str
    value: str


@app.patch("/plants/{plant_id}")
async def patch_plant(
    plant_id: int,
    patch: PlantPatch,
    user: User = Depends(require_permission("plants:write")),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await plants.update_plant(session, user.sub, plant_id, patch.field, patch.value)
    except plants.PlantError as e:
        raise HTTPException(400, str(e))
