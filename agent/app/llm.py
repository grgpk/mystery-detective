"""Thin LLM interface so game logic never depends on a vendor SDK directly.

`AnthropicLLM` is the real implementation. `ScriptedLLM` is deterministic and offline: used by
tests and as a dev fallback when no Anthropic credentials are configured.
"""

import os
from collections.abc import AsyncIterator, Callable
from typing import Protocol, TypeVar

import anthropic
from pydantic import BaseModel

PERSONA_MODEL = "claude-haiku-5-5"  # personas, topic classifier, statement extraction, scene narration
JUDGE_MODEL = "claude-opus-5-5"  # verdict narrative (and, in M4, case generation)

T = TypeVar("T", bound=BaseModel)
Message = dict  # {"role": "user" | "assistant", "content": str}


class LLMRefusal(Exception):
    pass


class LLM(Protocol):
    def stream(
        self, *, model: str, system: str, messages: list[Message], max_tokens: int, effort: str = "low"
    ) -> AsyncIterator[str]: ...

    async def parse(
        self, *, model: str, system: str, messages: list[Message], output_type: type[T], max_tokens: int = 1024
    ) -> T: ...


class AnthropicLLM:
    def __init__(self, client: anthropic.AsyncAnthropic | None = None):
        self.client = client or anthropic.AsyncAnthropic()

    async def stream(
        self, *, model: str, system: str, messages: list[Message], max_tokens: int, effort: str = "low"
    ) -> AsyncIterator[str]:
        async with self.client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            # The system prompt is stable for the whole game, so it is the cache prefix.
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=messages,
            output_config={"effort": effort},
        ) as stream:
            async for text in stream.text_stream:
                yield text
            final = await stream.get_final_message()
            if final.stop_reason == "refusal":
                raise LLMRefusal(model)

    async def parse(
        self, *, model: str, system: str, messages: list[Message], output_type: type[T], max_tokens: int = 1024
    ) -> T:
        response = await self.client.messages.parse(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
            output_format=output_type,
            output_config={"effort": "low"},
        )
        if response.stop_reason == "refusal" or response.parsed_output is None:
            raise LLMRefusal(model)
        return response.parsed_output


class ScriptedLLM:
    """Offline stand-in. `respond` maps (system, last user message) to the reply text."""

    def __init__(
        self,
        respond: Callable[[str, str], str] | None = None,
        parsers: dict[type, Callable[[str], BaseModel]] | None = None,
    ):
        self.respond = respond or _default_scripted_reply
        self.parsers = parsers or {}
        self.calls: list[dict] = []

    async def stream(
        self, *, model: str, system: str, messages: list[Message], max_tokens: int, effort: str = "low"
    ) -> AsyncIterator[str]:
        self.calls.append({"model": model, "system": system, "messages": messages})
        reply = self.respond(system, messages[-1]["content"])
        for word in reply.split(" "):
            yield word + " "

    async def parse(
        self, *, model: str, system: str, messages: list[Message], output_type: type[T], max_tokens: int = 1024
    ) -> T:
        self.calls.append({"model": model, "system": system, "messages": messages, "parse": output_type})
        if output_type in self.parsers:
            return self.parsers[output_type](messages[-1]["content"])  # type: ignore[return-value]
        return output_type.model_validate({})


def _default_scripted_reply(system: str, user: str) -> str:
    """Speaks whatever the turn context says must or may be said, so offline play stays coherent."""
    lines = [
        line.removeprefix("- ").strip()
        for line in user.splitlines()
        if line.startswith("- ") and ("SAY:" in line or "REVEAL:" in line)
    ]
    spoken = [line.split(":", 1)[1].strip() for line in lines]
    if system.lower().startswith("you are the narrator"):
        findings = [line.removeprefix("- ") for line in user.splitlines() if line.startswith("- ")]
        return " ".join(findings) if findings else user.splitlines()[-1]
    return " ".join(spoken) if spoken else "I really couldn't say, Inspector."


def default_llm() -> LLM:
    if os.getenv("LLM_MODE", "anthropic") == "scripted":
        return ScriptedLLM()
    return AnthropicLLM()
