"""Concrete LLM providers: Anthropic (Claude), OpenAI-compatible, and Ollama."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import anthropic
import httpx
import openai

from app.core.config import Settings
from app.core.logging import get_logger
from app.llm.base import ChatTurn, DemoLLM, LLMError, LLMProvider

log = get_logger(__name__)


class AnthropicLLM:
    """Claude via the official Anthropic SDK.

    Uses server-side refusal fallbacks (beta) so a safety-classifier decline is retried on
    a fallback model inside the same call, and checks stop_reason before using output.
    """

    name = "anthropic"
    is_live = True
    _BETAS = ["server-side-fallback-2026-07-01"]

    def __init__(self, api_key: str, model: str, effort: str, timeout: float) -> None:
        self.model = model
        self.effort = effort
        self._client = anthropic.AsyncAnthropic(api_key=api_key, timeout=timeout, max_retries=2)

    def _params(self, system: str, messages: list[ChatTurn], max_tokens: int) -> dict:
        return {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "output_config": {"effort": self.effort},
            "betas": self._BETAS,
            "fallbacks": "default",
        }

    @staticmethod
    def _wrap(exc: Exception) -> LLMError:
        if isinstance(exc, anthropic.AuthenticationError):
            log.error("anthropic: authentication failed")
            return LLMError("The language model rejected the configured credentials.")
        if isinstance(exc, anthropic.RateLimitError):
            return LLMError("The language model is rate limited. Please try again shortly.")
        if isinstance(exc, anthropic.APIStatusError):
            log.error("anthropic: status %s", exc.status_code)
            return LLMError("The language model returned an error.")
        if isinstance(exc, anthropic.APIConnectionError):
            return LLMError("The language model could not be reached.")
        return LLMError("The language model request failed.")

    async def complete(self, system: str, messages: list[ChatTurn], *, max_tokens: int) -> str:
        chunks = [c async for c in self.stream(system, messages, max_tokens=max_tokens)]
        return "".join(chunks)

    async def stream(self, system: str, messages: list[ChatTurn], *, max_tokens: int) -> AsyncIterator[str]:
        try:
            async with self._client.beta.messages.stream(**self._params(system, messages, max_tokens)) as s:
                async for text in s.text_stream:
                    yield text
                final = await s.get_final_message()
            if final.stop_reason == "refusal":
                raise LLMError("The language model declined to answer this request.")
        except LLMError:
            raise
        except anthropic.AnthropicError as exc:
            raise self._wrap(exc) from exc


class OpenAILLM:
    """OpenAI or any OpenAI-compatible endpoint (set OPENAI_BASE_URL)."""

    name = "openai"
    is_live = True

    def __init__(self, api_key: str, model: str, base_url: str | None, timeout: float) -> None:
        self.model = model
        self._client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=timeout, max_retries=2)

    async def complete(self, system: str, messages: list[ChatTurn], *, max_tokens: int) -> str:
        return "".join([c async for c in self.stream(system, messages, max_tokens=max_tokens)])

    async def stream(self, system: str, messages: list[ChatTurn], *, max_tokens: int) -> AsyncIterator[str]:
        payload = [{"role": "system", "content": system}] + [{"role": m.role, "content": m.content} for m in messages]
        try:
            response = await self._client.chat.completions.create(
                model=self.model, messages=payload, max_tokens=max_tokens, stream=True
            )
            async for event in response:
                if event.choices and event.choices[0].delta and event.choices[0].delta.content:
                    yield event.choices[0].delta.content
        except openai.AuthenticationError as exc:
            raise LLMError("The language model rejected the configured credentials.") from exc
        except openai.RateLimitError as exc:
            raise LLMError("The language model is rate limited. Please try again shortly.") from exc
        except openai.APIConnectionError as exc:
            raise LLMError("The language model could not be reached.") from exc
        except openai.OpenAIError as exc:
            raise LLMError("The language model returned an error.") from exc


class OllamaLLM:
    """Local models served by Ollama (https://ollama.com)."""

    name = "ollama"
    is_live = True

    def __init__(self, base_url: str, model: str, timeout: float) -> None:
        self.model = model
        self._base = base_url.rstrip("/")
        self._timeout = timeout

    async def complete(self, system: str, messages: list[ChatTurn], *, max_tokens: int) -> str:
        return "".join([c async for c in self.stream(system, messages, max_tokens=max_tokens)])

    async def stream(self, system: str, messages: list[ChatTurn], *, max_tokens: int) -> AsyncIterator[str]:
        body = {
            "model": self.model,
            "stream": True,
            "messages": [{"role": "system", "content": system}]
            + [{"role": m.role, "content": m.content} for m in messages],
            "options": {"num_predict": max_tokens, "temperature": 0.2},
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout, trust_env=False) as client:
                async with client.stream("POST", f"{self._base}/api/chat", json=body) as response:
                    if response.status_code != 200:
                        raise LLMError("The local language model returned an error.")
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        data = json.loads(line)
                        if data.get("error"):
                            raise LLMError("The local language model returned an error.")
                        piece = (data.get("message") or {}).get("content")
                        if piece:
                            yield piece
                        if data.get("done"):
                            break
        except LLMError:
            raise
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise LLMError("The local language model could not be reached.") from exc


def build_llm(settings: Settings) -> LLMProvider:
    choice = settings.llm_provider
    if choice == "auto":
        if settings.anthropic_api_key:
            choice = "anthropic"
        elif settings.openai_api_key:
            choice = "openai"
        elif settings.ollama_base_url:
            choice = "ollama"
        else:
            choice = "demo"
    if choice == "anthropic" and settings.anthropic_api_key:
        return AnthropicLLM(settings.anthropic_api_key, settings.anthropic_model, settings.anthropic_effort,
                            settings.llm_timeout_seconds)
    if choice == "openai" and settings.openai_api_key:
        return OpenAILLM(settings.openai_api_key, settings.openai_model, settings.openai_base_url,
                         settings.llm_timeout_seconds)
    if choice == "ollama" and settings.ollama_base_url:
        return OllamaLLM(settings.ollama_base_url, settings.ollama_model, settings.llm_timeout_seconds)
    return DemoLLM()
