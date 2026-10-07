"""LLM interface with tool-use support: the real (Anthropic) client and a scripted fake for tests.

Model names come from env vars (ADR-006); nothing here is hard-coded and tests never touch the network.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Protocol


class LLMConfigError(RuntimeError):
    """Raised when the real LLM is not configured (e.g. missing model env var)."""


class ScriptExhaustedError(RuntimeError):
    """Raised when a ScriptedLLM is called after its script ran out."""


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=lambda: {"type": "object", "properties": {}})


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMResponse:
    """Either plain text, or a request to call one or more tools (optionally with text)."""

    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)


class LLM(Protocol):
    def complete(self, system: str, messages: list[dict[str, Any]], tools: list[ToolSpec]) -> LLMResponse: ...


class AnthropicLLM:
    """Real LLM via the ``anthropic`` library. Model name is read from an env var at construction."""

    def __init__(
        self,
        model: str | None = None,
        *,
        model_env: str = "MODEL_REASONING",
        client: Any = None,
        max_tokens: int = 2048,
    ) -> None:
        if model is None:
            model = (os.environ.get(model_env) or "").strip()
            if not model:
                raise LLMConfigError(f"Environment variable {model_env} is not set; cannot create the real LLM.")
        self.model = model
        self.max_tokens = max_tokens
        if client is None:
            import anthropic

            client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY; no network call here
        self._client = client

    def complete(self, system: str, messages: list[dict[str, Any]], tools: list[ToolSpec]) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = [
                {"name": t.name, "description": t.description, "input_schema": t.input_schema} for t in tools
            ]
        resp = self._client.messages.create(**kwargs)
        texts: list[str] = []
        calls: list[ToolCall] = []
        for block in resp.content:
            if block.type == "text":
                texts.append(block.text)
            elif block.type == "tool_use":
                calls.append(ToolCall(id=block.id, name=block.name, arguments=dict(block.input)))
        return LLMResponse(text="".join(texts), tool_calls=calls)


class ScriptedLLM:
    """Fake LLM for tests: returns scripted responses in order; errors when the script runs out."""

    def __init__(self, script: list[LLMResponse | str]) -> None:
        self._script = [r if isinstance(r, LLMResponse) else LLMResponse(text=r) for r in script]
        self._i = 0
        self.calls: list[dict[str, Any]] = []

    def complete(self, system: str, messages: list[dict[str, Any]], tools: list[ToolSpec]) -> LLMResponse:
        self.calls.append({"system": system, "messages": list(messages), "tools": list(tools)})
        if self._i >= len(self._script):
            raise ScriptExhaustedError(f"ScriptedLLM script exhausted after {len(self._script)} responses")
        resp = self._script[self._i]
        self._i += 1
        return resp
