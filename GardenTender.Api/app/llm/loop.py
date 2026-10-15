"""Provider-agnostic chat loop. `/chat` depends only on `run_chat`.

Stateless resume: when the model requests a call that needs the client (a `confirm=True` server tool, or any
`runs_on="device"` tool), the loop stops and returns the history plus the pending calls. The client sends the
history back with `decisions` (server tools) and `device_results` (device tools) to resume. Forged history
gains no extra capability: every executed call is still permission-checked and validated here.
"""
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth import User
from app.llm.base import LlmProvider
from app.services.plants import PlantError
from app.tools.registry import TOOLS, tools_for


@dataclass
class PendingCall:
    id: str
    name: str
    input: dict
    runs_on: str = "server"
    confirm: bool = False


@dataclass
class DeviceResult:
    content: str
    is_error: bool = False


@dataclass
class ChatResult:
    history: list[dict]
    reply: str = ""
    pending: list[PendingCall] = field(default_factory=list)


def _system_prompt(tz_name: str | None) -> str:
    try:
        tz = ZoneInfo(tz_name) if tz_name else timezone.utc
    except (ZoneInfoNotFoundError, ValueError):
        tz = timezone.utc
    now = datetime.now(tz).isoformat(timespec="minutes")
    return (
        "You are the GardenTender assistant, helping the user care for their plants. "
        f"The user's current local time is {now} ({tz_name or 'UTC'}). Use the provided tools to read or "
        "change the user's data; never guess ids. Times you pass to tools are local ISO 8601 "
        "(e.g. 2026-10-15T09:00). Be brief."
    )


async def _execute(maker: async_sessionmaker[AsyncSession], user: User, name: str, raw_input: dict) -> tuple[str, bool]:
    """Runs one tool call as the user. Returns (content, is_error)."""
    tool = TOOLS.get(name)
    if tool is None or tool.permission not in user.permissions:
        return f"Tool {name!r} is not available.", True
    try:
        args = tool.input_model.model_validate(raw_input)
    except ValidationError as e:
        return f"Invalid arguments: {e.errors(include_url=False, include_context=False)}", True
    try:
        # Short-lived session per tool call: no connection is held while waiting on the LLM.
        async with maker() as session:
            return json.dumps(await tool.handler(session, user.sub, args)), False
    except PlantError as e:
        return str(e), True


def _tool_uses(message: dict) -> list[dict]:
    return [b for b in message["content"] if b["type"] == "tool_use"]


def _result_block(call_id: str, content: str, is_error: bool) -> dict:
    return {"type": "tool_result", "tool_use_id": call_id, "content": content, "is_error": is_error}


def _validated(tool, raw_input: dict):
    """Returns (args, None) or (None, error message)."""
    try:
        return tool.input_model.model_validate(raw_input), None
    except ValidationError as e:
        return None, f"Invalid arguments: {e.errors(include_url=False, include_context=False)}"


def _needs_client(user: User, call: dict) -> bool:
    """True if the call can't be answered by the server alone."""
    tool = TOOLS.get(call["name"])
    if tool is None or tool.permission not in user.permissions:
        return False  # answered with an error in _resolve
    if tool.runs_on == "device":
        return _validated(tool, call["input"])[1] is None  # invalid args are bounced back to the model
    return tool.confirm


async def _resolve(
    maker: async_sessionmaker[AsyncSession],
    user: User,
    calls: list[dict],
    decisions: dict[str, bool],
    device_results: dict[str, DeviceResult],
) -> dict:
    """Builds the user message answering `calls`. Missing decisions count as declined."""
    results = []
    for call in calls:
        tool = TOOLS.get(call["name"])
        if tool is not None and tool.permission in user.permissions and tool.runs_on == "device":
            _, error = _validated(tool, call["input"])
            if error:
                results.append(_result_block(call["id"], error, True))
                continue
            r = device_results.get(call["id"]) or DeviceResult("The device did not run this action.", True)
            results.append(_result_block(call["id"], r.content, r.is_error))
        elif tool is not None and tool.confirm and not decisions.get(call["id"], False):
            results.append(_result_block(call["id"], "The user declined this action.", True))
        else:
            content, is_error = await _execute(maker, user, call["name"], call["input"])
            results.append(_result_block(call["id"], content, is_error))
    return {"role": "user", "content": results}


async def run_chat(
    maker: async_sessionmaker[AsyncSession],
    user: User,
    history: list[dict],
    decisions: dict[str, bool],
    provider: LlmProvider,
    max_steps: int,
    device_results: dict[str, DeviceResult] | None = None,
    tz_name: str | None = None,
) -> ChatResult:
    device_results = device_results or {}
    history = list(history)
    available = tools_for(user.permissions)

    # Resume: the last assistant turn has tool calls awaiting results.
    if history and history[-1]["role"] == "assistant" and _tool_uses(history[-1]):
        history.append(await _resolve(maker, user, _tool_uses(history[-1]), decisions, device_results))

    for _ in range(max_steps):
        blocks = await provider.chat(_system_prompt(tz_name), history, available)
        history.append({"role": "assistant", "content": blocks})
        calls = _tool_uses(history[-1])
        if not calls:
            text = "".join(b["text"] for b in blocks if b["type"] == "text")
            return ChatResult(history=history, reply=text)
        client_calls = [c for c in calls if _needs_client(user, c)]
        if client_calls:
            return ChatResult(
                history=history,
                pending=[
                    PendingCall(c["id"], c["name"], c["input"], TOOLS[c["name"]].runs_on, TOOLS[c["name"]].confirm)
                    for c in client_calls
                ],
            )
        history.append(await _resolve(maker, user, calls, {}, {}))

    return ChatResult(history=history, reply="I couldn't finish that. Please try again.")
