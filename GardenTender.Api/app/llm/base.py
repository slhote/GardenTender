"""Provider boundary.

Messages use a neutral block format (matches Claude's): {"role", "content": [blocks]} where a block is
{"type": "text", "text"}, {"type": "tool_use", "id", "name", "input"} or
{"type": "tool_result", "tool_use_id", "content", "is_error"}. Other providers translate at this boundary.
"""
from typing import Protocol

from app.tools.registry import Tool


class LlmProvider(Protocol):
    async def chat(self, system: str, messages: list[dict], tools: list[Tool]) -> list[dict]:
        """Returns the assistant's content blocks (text and/or tool_use)."""
        ...


class LlmUnavailable(Exception):
    """The model backend couldn't be reached or returned something unusable."""
