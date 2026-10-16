import asyncio
import json

import httpx

from app.llm.ollama import OllamaProvider
from app.tools.registry import TOOLS


def provider_with(handler):
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return OllamaProvider("http://ollama:11434", "qwen2.5:3b", client)


def test_tool_call_gets_generated_id_and_tools_are_sent():
    seen = {}

    def handler(request):
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"message": {"content": "", "tool_calls": [
            {"function": {"name": "list_plants", "arguments": {}}}]}})

    p = provider_with(handler)
    blocks = asyncio.run(p.chat("sys", [{"role": "user", "content": [{"type": "text", "text": "hi"}]}],
                                [TOOLS["list_plants"]]))
    assert blocks[0]["type"] == "tool_use" and blocks[0]["name"] == "list_plants"
    assert blocks[0]["id"].startswith("call_")
    assert seen["model"] == "qwen2.5:3b" and seen["stream"] is False
    assert seen["tools"][0]["function"]["name"] == "list_plants"
    assert seen["messages"][0] == {"role": "system", "content": "sys"}


def test_history_with_tool_result_is_translated():
    seen = {}

    def handler(request):
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"message": {"content": "You have 2 plants."}})

    history = [
        {"role": "user", "content": [{"type": "text", "text": "plants?"}]},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "c1", "name": "list_plants", "input": {}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "c1", "content": "[]", "is_error": False}]},
    ]
    blocks = asyncio.run(provider_with(handler).chat("sys", history, []))
    assert blocks == [{"type": "text", "text": "You have 2 plants."}]
    roles = [m["role"] for m in seen["messages"]]
    assert roles == ["system", "user", "assistant", "tool"]
    assert seen["messages"][2]["tool_calls"][0]["function"]["name"] == "list_plants"
    assert seen["messages"][3] == {"role": "tool", "tool_name": "list_plants", "content": "[]"}
    assert "tools" not in seen


def test_string_arguments_are_parsed():
    def handler(request):
        return httpx.Response(200, json={"message": {"content": "", "tool_calls": [
            {"function": {"name": "set_reminder", "arguments": '{"text": "x", "time": "2026-10-15T09:00"}'}}]}})

    blocks = asyncio.run(provider_with(handler).chat("s", [], []))
    assert blocks[0]["input"] == {"text": "x", "time": "2026-10-15T09:00"}


def test_unreachable_ollama_raises_llm_unavailable():
    import pytest
    from app.llm.base import LlmUnavailable

    def handler(request):
        raise httpx.ConnectError("down")

    with pytest.raises(LlmUnavailable):
        asyncio.run(provider_with(handler).chat("s", [], []))
