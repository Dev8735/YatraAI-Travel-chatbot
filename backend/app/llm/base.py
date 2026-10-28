"""Provider-neutral LLM interface."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal, Protocol


@dataclass(frozen=True)
class ChatTurn:
    role: Literal["user", "assistant"]
    content: str


class LLMError(Exception):
    """Raised by providers with a user-safe message; details go to logs only."""


class LLMProvider(Protocol):
    name: str
    model: str
    is_live: bool  # False for the deterministic demo/extractive mode

    async def complete(self, system: str, messages: list[ChatTurn], *, max_tokens: int) -> str: ...

    def stream(self, system: str, messages: list[ChatTurn], *, max_tokens: int) -> AsyncIterator[str]: ...


class DemoLLM:
    """Marker provider: the RAG layer answers extractively, quoting retrieved text."""

    name = "demo"
    model = "extractive"
    is_live = False

    async def complete(self, system: str, messages: list[ChatTurn], *, max_tokens: int) -> str:
        raise LLMError("No language model is configured.")

    async def stream(self, system: str, messages: list[ChatTurn], *, max_tokens: int) -> AsyncIterator[str]:
        raise LLMError("No language model is configured.")
        yield ""  # pragma: no cover
