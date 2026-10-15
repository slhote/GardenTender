import anthropic
from anthropic import AsyncAnthropic

from app.llm.base import LlmUnavailable
from app.tools.registry import Tool


class ClaudeProvider:
    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise LlmUnavailable("ANTHROPIC_API_KEY is not set")
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    async def chat(self, system: str, messages: list[dict], tools: list[Tool]) -> list[dict]:
        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                system=system,
                messages=messages,
                tools=[
                    {"name": t.name, "description": t.description, "input_schema": t.json_schema()}
                    for t in tools
                ],
            )
        except anthropic.APIError as e:
            raise LlmUnavailable(f"Claude request failed: {e}") from e
        blocks = []
        for b in response.content:
            if b.type == "text":
                blocks.append({"type": "text", "text": b.text})
            elif b.type == "tool_use":
                blocks.append({"type": "tool_use", "id": b.id, "name": b.name, "input": b.input})
        return blocks
