from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.access import GardenAccess
from app.auth import User, get_current_user
from app.config import Settings, get_settings
from app.db import get_sessionmaker
from app.dependencies import require_garden
from app.llm.base import LlmProvider
from app.llm.claude import ClaudeProvider
from app.llm.loop import DeviceResult, run_chat
from app.llm.ollama import OllamaProvider
from app.roles import GardenPermission
from app.tools.registry import ToolContext

router = APIRouter(tags=["chat"])


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


def get_provider(req: ChatRequest, s: Settings = Depends(get_settings)) -> LlmProvider:
    if s.llm_provider == "claude":
        return ClaudeProvider(s.anthropic_api_key, s.llm_model)
    if s.llm_provider == "ollama":
        model = req.model or s.llm_model
        if model != s.llm_model and model not in s.ollama_models:
            raise HTTPException(400, f"Unknown model {model!r}.")
        return OllamaProvider(s.ollama_base_url, model)
    raise HTTPException(500, f"Unknown LLM provider {s.llm_provider!r}")


@router.get("/models")
async def list_models(_: User = Depends(get_current_user), s: Settings = Depends(get_settings)):
    if s.llm_provider == "ollama":
        models = s.ollama_models if s.llm_model in s.ollama_models else [s.llm_model, *s.ollama_models]
        return {"models": models, "default": s.llm_model}
    return {"models": [s.llm_model], "default": s.llm_model}


@router.post("/gardens/{garden_id}/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    access: GardenAccess = Depends(require_garden(GardenPermission.CHAT, allow_override=False)),
    provider: LlmProvider = Depends(get_provider),
    maker: async_sessionmaker[AsyncSession] = Depends(get_sessionmaker),
    s: Settings = Depends(get_settings),
):
    history = list(req.history)
    if req.message:
        history.append({"role": "user", "content": [{"type": "text", "text": req.message}]})
    result = await run_chat(
        maker,
        ToolContext(access.garden.id, access.actor, access.role),
        history,
        req.decisions,
        provider,
        s.max_tool_steps,
        device_results={k: DeviceResult(v.content, v.is_error) for k, v in req.device_results.items()},
        tz_name=req.timezone,
    )
    return ChatResponse(
        history=result.history,
        reply=result.reply,
        pending=[PendingOut(id=p.id, name=p.name, input=p.input, runs_on=p.runs_on, confirm=p.confirm) for p in result.pending],
    )
