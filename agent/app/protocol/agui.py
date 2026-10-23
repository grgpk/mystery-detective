"""Thin adapter over the AG-UI Python SDK (ag-ui-protocol). Game code builds events only through here."""

import json
import uuid
from collections.abc import AsyncIterator

import jsonpatch
from ag_ui.core import (
    BaseEvent,
    EventType,
    RunErrorEvent,
    RunFinishedEvent,
    RunStartedEvent,
    StateDeltaEvent,
    StateSnapshotEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
    ToolCallArgsEvent,
    ToolCallEndEvent,
    ToolCallResultEvent,
    ToolCallStartEvent,
)

from app.a2ui.catalog import surface_operations

A2UI_OPERATIONS_KEY = "a2ui_operations"  # what CopilotRuntime's A2UI middleware looks for in tool results
SHOW_UI_TOOL = "show_ui"


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def speaker_message_id(speaker: str) -> str:
    """Message ids carry the speaker ("narrator" or a suspect id) so the UI can label dialogue."""
    return f"msg-{speaker}-{uuid.uuid4().hex[:10]}"


def run_started(thread_id: str, run_id: str) -> BaseEvent:
    return RunStartedEvent(type=EventType.RUN_STARTED, thread_id=thread_id, run_id=run_id)


def run_finished(thread_id: str, run_id: str) -> BaseEvent:
    return RunFinishedEvent(type=EventType.RUN_FINISHED, thread_id=thread_id, run_id=run_id)


def run_error(message: str, code: str = "game_error") -> BaseEvent:
    return RunErrorEvent(type=EventType.RUN_ERROR, message=message, code=code)


def state_snapshot(state: dict) -> BaseEvent:
    return StateSnapshotEvent(type=EventType.STATE_SNAPSHOT, snapshot=state)


def state_delta(before: dict, after: dict) -> BaseEvent | None:
    patch = jsonpatch.make_patch(before, after).patch
    return StateDeltaEvent(type=EventType.STATE_DELTA, delta=patch) if patch else None


class TextStream:
    """Streams one assistant message token by token."""

    def __init__(self, speaker: str):
        self.message_id = speaker_message_id(speaker)
        self.started = False

    def start(self) -> BaseEvent:
        self.started = True
        return TextMessageStartEvent(type=EventType.TEXT_MESSAGE_START, message_id=self.message_id, role="assistant")

    def chunk(self, delta: str) -> BaseEvent:
        return TextMessageContentEvent(type=EventType.TEXT_MESSAGE_CONTENT, message_id=self.message_id, delta=delta)

    def end(self) -> BaseEvent:
        return TextMessageEndEvent(type=EventType.TEXT_MESSAGE_END, message_id=self.message_id)


async def text_message(speaker: str, text: str) -> AsyncIterator[BaseEvent]:
    stream = TextStream(speaker)
    yield stream.start()
    yield stream.chunk(text)
    yield stream.end()


def a2ui_surface(surface_id: str, components: list[dict]) -> list[BaseEvent]:
    """Emits a surface as a completed `show_ui` tool call whose result carries A2UI operations.

    CopilotRuntime's A2UI middleware turns the result into an `a2ui-surface` activity message.
    """
    tool_call_id = new_id("ui")
    parent_id = speaker_message_id("ui")
    result = json.dumps({A2UI_OPERATIONS_KEY: surface_operations(surface_id, components)})
    return [
        ToolCallStartEvent(
            type=EventType.TOOL_CALL_START,
            tool_call_id=tool_call_id,
            tool_call_name=SHOW_UI_TOOL,
            parent_message_id=parent_id,
        ),
        ToolCallArgsEvent(
            type=EventType.TOOL_CALL_ARGS, tool_call_id=tool_call_id, delta=json.dumps({"surfaceId": surface_id})
        ),
        ToolCallEndEvent(type=EventType.TOOL_CALL_END, tool_call_id=tool_call_id),
        ToolCallResultEvent(
            type=EventType.TOOL_CALL_RESULT,
            message_id=new_id("tool"),
            tool_call_id=tool_call_id,
            content=result,
            role="tool",
        ),
    ]
