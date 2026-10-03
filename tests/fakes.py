"""Scripted LLM client for offline tests — never calls the network."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.llm import LLMResponse, LLMToolCall


def tool(name: str, arguments: dict[str, Any] | None = None, call_id: str | None = None) -> LLMToolCall:
    return LLMToolCall(
        id=call_id or f"call_{name}",
        name=name,
        arguments=arguments or {},
    )


def round_with(*tool_calls: LLMToolCall, content: str | None = None) -> LLMResponse:
    return LLMResponse(content=content, tool_calls=list(tool_calls))


DONE = LLMResponse(content="ok", tool_calls=[])


@dataclass
class ScriptedLLM:
    """Returns pre-scripted completions in order. Records every prompt for isolation checks."""

    scripts: list[LLMResponse]
    index: int = 0
    prompts: list[list[dict[str, Any]]] = field(default_factory=list)
    tools_seen: list[list[dict[str, Any]]] = field(default_factory=list)

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        self.prompts.append(messages)
        self.tools_seen.append(tools)
        if self.index >= len(self.scripts):
            return DONE
        response = self.scripts[self.index]
        self.index += 1
        return response

    @property
    def exposed_tool_names(self) -> set[str]:
        if not self.tools_seen:
            return set()
        names: set[str] = set()
        for tools in self.tools_seen:
            for item in tools:
                names.add(item["function"]["name"])
        return names
