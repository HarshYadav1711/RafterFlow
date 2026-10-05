"""Configurable OpenAI-compatible chat client. Tests inject a fake implementation."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.config import Settings, get_settings

# Cap sleeps so a single enquiry cannot hang past typical eval timeouts.
_MAX_RETRY_SLEEP_SECONDS = 25.0
_MAX_ATTEMPTS = 4


class LLMProviderError(RuntimeError):
    """Provider/transport failure that is not a business-rule outcome."""


class LLMRateLimitError(LLMProviderError):
    """Provider rate limit exhausted (after bounded retries)."""

    def __init__(self, message: str, *, retry_after_seconds: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


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


def _retry_after_seconds(exc: BaseException) -> float | None:
    """Best-effort extract of provider retry delay from headers or message text."""
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None) or {}
    raw = headers.get("retry-after") or headers.get("Retry-After")
    if raw is not None:
        try:
            return max(0.0, float(raw))
        except (TypeError, ValueError):
            pass

    text = str(exc)
    match = re.search(
        r"try again in\s+(\d+)m\s*([\d.]+)s",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return float(match.group(1)) * 60.0 + float(match.group(2))
    match = re.search(r"try again in\s+([\d.]+)\s*s", text, flags=re.IGNORECASE)
    if match:
        return float(match.group(1))
    return None


def _parse_tool_calls(message: Any) -> list[LLMToolCall]:
    tool_calls: list[LLMToolCall] = []
    for tc in message.tool_calls or []:
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
    return tool_calls


class OpenAICompatibleClient:
    """Thin wrapper around the official openai SDK (works with Groq/Ollama-compatible URLs)."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        from openai import APIError, OpenAI, RateLimitError

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

        last_rate_limit: RateLimitError | None = None
        for attempt in range(_MAX_ATTEMPTS):
            try:
                completion = client.chat.completions.create(**kwargs)
                message = completion.choices[0].message
                return LLMResponse(
                    content=message.content,
                    tool_calls=_parse_tool_calls(message),
                )
            except RateLimitError as exc:
                last_rate_limit = exc
                wait = _retry_after_seconds(exc)
                # Long TPD windows cannot be slept through inside one enquiry.
                if wait is not None and wait > _MAX_RETRY_SLEEP_SECONDS:
                    raise LLMRateLimitError(
                        f"LLM rate limit exceeded; retry after about {wait:.0f}s. {exc}",
                        retry_after_seconds=wait,
                    ) from exc
                if attempt >= _MAX_ATTEMPTS - 1:
                    break
                sleep_for = wait if wait is not None else float(2**attempt)
                time.sleep(min(sleep_for, _MAX_RETRY_SLEEP_SECONDS))
            except APIError as exc:
                raise LLMProviderError(f"LLM provider error: {exc}") from exc

        assert last_rate_limit is not None
        wait = _retry_after_seconds(last_rate_limit)
        raise LLMRateLimitError(
            f"LLM rate limit exceeded after {_MAX_ATTEMPTS} attempts. {last_rate_limit}",
            retry_after_seconds=wait,
        )


def get_llm_client() -> LLMClient:
    return OpenAICompatibleClient()
