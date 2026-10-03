"""Configurable OpenAI-compatible chat client. Tests inject a fake implementation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.config import Settings, get_settings


@dataclass(frozen=True, slots=True)
class LLMToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class LLMResponse:
    content: str | None = None
    tool_calls: list[LLMToolCall] = field(default_factory=list)


class LLMClient(Protocol):
    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        """One tool-capable chat completion turn."""


class OpenAICompatibleClient:
    """Thin wrapper around the official openai SDK (works with Groq/Ollama-compatible URLs)."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        from openai import OpenAI

        if not self.settings.llm_api_key and not self.settings.llm_base_url:
            raise RuntimeError(
                "LLM is not configured. Set LLM_BASE_URL / LLM_API_KEY / LLM_MODEL "
                "(or inject a test client)."
            )

        client = OpenAI(
            api_key=self.settings.llm_api_key or "not-needed",
            base_url=self.settings.llm_base_url or None,
        )
        kwargs: dict[str, Any] = {
            "model": self.settings.llm_model or "gpt-4o-mini",
            "messages": messages,
            "temperature": 0,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        completion = client.chat.completions.create(**kwargs)
        message = completion.choices[0].message
        tool_calls: list[LLMToolCall] = []
        for tc in message.tool_calls or []:
            import json

            raw_args = tc.function.arguments or "{}"
            try:
                parsed = json.loads(raw_args)
            except json.JSONDecodeError:
                parsed = {}
            if not isinstance(parsed, dict):
                parsed = {}
            tool_calls.append(
                LLMToolCall(id=tc.id, name=tc.function.name, arguments=parsed)
            )
        return LLMResponse(content=message.content, tool_calls=tool_calls)


def get_llm_client() -> LLMClient:
    return OpenAICompatibleClient()
