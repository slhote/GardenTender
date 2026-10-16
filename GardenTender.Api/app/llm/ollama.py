"""Ollama provider (non-streaming `/api/chat`).

Temporary hand-written adapter. LangChain's `ChatOllama` covers all of this (tool-call format, call ids,
message translation), so this file is replaced when LangChain is adopted; see PLAN.md.
"""
import json
import uuid

import httpx

from app.llm.base import LlmUnavailable
from app.tools.registry import Tool


class OllamaProvider:
    def __init__(self, base_url: str, model: str, client: httpx.AsyncClient | None = None):
        self._base_url = base_url.rstrip("/")
        self._model = model
        # Small local models on CPU can be slow.
        self._client = client or httpx.AsyncClient(timeout=180)

    async def chat(self, system: str, messages: list[dict], tools: list[Tool]) -> list[dict]:
        payload = {
            "model": self._model,
            "stream": False,
            "messages": [{"role": "system", "content": system}, *_to_ollama(messages)],
        }
        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {"name": t.name, "description": t.description, "parameters": t.json_schema()},
                }
                for t in tools
            ]
        try:
            response = await self._client.post(f"{self._base_url}/api/chat", json=payload)
            response.raise_for_status()
            message = response.json()["message"]
        except (httpx.HTTPError, KeyError, ValueError) as e:
            raise LlmUnavailable(f"Ollama request failed: {e}") from e

        blocks = []
        if message.get("content"):
            blocks.append({"type": "text", "text": message["content"]})
        for call in message.get("tool_calls") or []:
            fn = call["function"]
            args = fn.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except ValueError:
                    args = {}
            # Ollama doesn't return call ids, but the resume flow keys on them, so generate one.
            blocks.append({"type": "tool_use", "id": f"call_{uuid.uuid4().hex[:12]}", "name": fn["name"], "input": args})
        return blocks


def _to_ollama(messages: list[dict]) -> list[dict]:
    """Neutral blocks (see llm/base.py) -> Ollama chat messages."""
    names: dict[str, str] = {}  # tool_use id -> tool name, for naming tool results
    out: list[dict] = []
    for m in messages:
        blocks = m["content"]
        if m["role"] == "assistant":
            text = "".join(b["text"] for b in blocks if b["type"] == "text")
            calls = [b for b in blocks if b["type"] == "tool_use"]
            for b in calls:
                names[b["id"]] = b["name"]
            msg: dict = {"role": "assistant", "content": text}
            if calls:
                msg["tool_calls"] = [{"function": {"name": b["name"], "arguments": b["input"]}} for b in calls]
            out.append(msg)
        else:
            for b in blocks:
                if b["type"] == "tool_result":
                    out.append({"role": "tool", "tool_name": names.get(b["tool_use_id"], ""), "content": b["content"]})
                elif b["type"] == "text":
                    out.append({"role": "user", "content": b["text"]})
    return out
