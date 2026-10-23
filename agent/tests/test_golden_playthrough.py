"""Plays Ashford Manor end to end through the AG-UI event stream with an offline LLM."""

import json
import uuid

import jsonpatch
import pytest
from ag_ui.core import EventType, RunAgentInput
from ag_ui.encoder import EventEncoder

from app.agents.classifier import TopicGuess
from app.agents.extractor import ExtractedClaim
from app.game import GameMaster
from app.llm import ScriptedLLM
from app.store.repo import InMemoryRepo


class Client:
    """Minimal AG-UI client: applies snapshots/deltas and collects messages and surfaces."""

    def __init__(self, game: GameMaster, owner: str = "player-1"):
        self.game, self.owner = game, owner
        self.thread_id = f"thread-{uuid.uuid4().hex[:8]}"
        self.state: dict = {}
        self.messages: dict[str, str] = {}
        self.surfaces: list[tuple[str, dict]] = []
        self.errors: list[str] = []

    async def act(self, action: dict | None = None) -> list:
        action = action or {"type": "start", "caseId": "ashford_manor"}
        run_input = RunAgentInput(
            thread_id=self.thread_id,
            run_id=uuid.uuid4().hex,
            state=self.state,
            messages=[],
            tools=[],
            context=[],
            forwarded_props={"gameAction": action},
        )
        events = [e async for e in self.game.run(run_input, self.owner)]
        assert events[0].type == EventType.RUN_STARTED
        encoder = EventEncoder()
        for event in events:
            e = json.loads(encoder.encode(event).removeprefix("data: "))  # exactly what the browser receives
            if e["type"] == "STATE_SNAPSHOT":
                self.state = e["snapshot"]
            elif e["type"] == "STATE_DELTA":
                self.state = jsonpatch.apply_patch(self.state, e["delta"])
            elif e["type"] == "TEXT_MESSAGE_CONTENT":
                self.messages[e["messageId"]] = self.messages.get(e["messageId"], "") + e["delta"]
            elif e["type"] == "TOOL_CALL_RESULT":
                ops = json.loads(e["content"])["a2ui_operations"]
                root = next(c for c in ops[1]["updateComponents"]["components"] if c["id"] == "root")
                self.surfaces.append((ops[0]["createSurface"]["surfaceId"], root))
            elif e["type"] == "RUN_ERROR":
                self.errors.append(e["message"])
        return events

    def surface_components(self) -> list[str]:
        return [root["component"] for _, root in self.surfaces]

    def statement(self, text_fragment: str) -> str:
        return next(s["id"] for s in self.state["statements"] if text_fragment in s["text"])


@pytest.fixture
def game():
    llm = ScriptedLLM(parsers={ExtractedClaim: lambda _: ExtractedClaim(), TopicGuess: lambda _: TopicGuess()})
    return GameMaster(llm, InMemoryRepo())


async def test_full_game_is_solvable(game):
    client = Client(game)
    await client.act()
    assert client.state["phase"] == "briefing"
    assert client.surface_components() == ["CaseBriefing"]

    await client.act({"type": "begin"})
    assert client.state["phase"] == "investigating"
    assert {"Stack", "NarrationBlock"} <= set(client.surface_components())

    await client.act({"type": "interrogate", "suspectId": "s2", "question": "Did you go into the garden tonight?"})
    assert client.state["turnsLeft"] == 14
    garden_lie = client.statement("never set foot in the garden")
    assert any("never set foot in the garden" in m for m in client.messages.values())

    await client.act({"type": "examine", "locationId": "guest_wing"})
    assert {c["id"] for c in client.state["clues"]} == {"c3", "c13"}
    assert client.surfaces[-1][1]["component"] == "Stack"

    await client.act({"type": "examine", "locationId": "study"})

    await client.act({"type": "confront", "suspectId": "s2", "items": [garden_lie, "c3"]})
    assert client.state["suspects"][1]["composure"] == 70
    assert client.state["lastContradiction"] == {"from": garden_lie, "to": "c3"}
    assert "c9" in {c["id"] for c in client.state["clues"]}
    assert "ClueCard" in client.surface_components()
    assert not any("REVEAL:" in m or "SAY:" in m for m in client.messages.values())

    await client.act(
        {"type": "accuse", "accusation": {"suspectId": "s2", "motiveId": "inheritance", "evidence": ["c3", "c5", "c9"]}}
    )
    verdict = client.state["verdict"]
    assert client.state["phase"] == "ended"
    assert verdict["score"]["total"] == 100
    assert verdict["culpritName"] == "Henry Ashford"
    assert client.surface_components()[-1] == "VerdictScreen"
    assert client.errors == []


async def test_rule_violations_are_narrated_not_crashes(game):
    client = Client(game)
    await client.act()
    await client.act({"type": "examine", "locationId": "ballroom"})
    assert any("no such place" in m for m in client.messages.values())
    assert client.state["turnsLeft"] == 15
    await client.act(
        {"type": "accuse", "accusation": {"suspectId": "s2", "motiveId": "inheritance", "evidence": ["c9"]}}
    )
    assert client.state["phase"] != "ended"


async def test_board_is_sanitized(game):
    client = Client(game)
    await client.act()
    await client.act({"type": "examine", "locationId": "guest_wing"})
    await client.act(
        {"type": "sync_board", "board": {"pins": ["c3", "c5"], "links": [{"from": "c3", "to": "c5"}], "notes": "hm"}}
    )
    await client.act({"type": "start"})
    assert client.state["board"] == {"pins": ["c3"], "links": [], "notes": "hm"}


async def test_another_session_cannot_hijack_a_thread(game):
    owner = Client(game)
    await owner.act()
    intruder = Client(game, owner="someone-else")
    intruder.thread_id = owner.thread_id
    await intruder.act({"type": "examine", "locationId": "study"})
    assert intruder.errors


async def test_reconnect_resends_snapshot_and_board(game):
    client = Client(game)
    await client.act()
    await client.act({"type": "begin"})
    client.state, client.surfaces = {}, []
    await client.act({"type": "start"})
    assert client.state["phase"] == "investigating"
    assert len([s for s, _ in client.surfaces if s.startswith(("roster", "map"))]) == 2


async def test_api_outage_degrades_instead_of_crashing():
    """No credit / API down: every LLM call fails, but the turn still completes with fallback lines."""
    import anthropic
    import httpx2

    class DownLLM(ScriptedLLM):
        def _fail(self):
            request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
            raise anthropic.BadRequestError(
                "credit balance too low", response=httpx2.Response(400, request=request), body=None
            )

        async def stream(self, **kwargs):
            self._fail()
            yield ""

        async def parse(self, **kwargs):
            self._fail()

    client = Client(GameMaster(DownLLM(), InMemoryRepo()))
    await client.act()
    await client.act({"type": "interrogate", "suspectId": "s2", "question": "How do you feel tonight?"})
    await client.act({"type": "examine", "locationId": "study"})
    assert client.errors == []
    assert client.state["turnsLeft"] == 13
    assert any("library reading all evening" in m for m in client.messages.values())


async def test_hint_costs_two_turns_and_shows_the_sergeant(game):
    client = Client(game)
    await client.act()
    await client.act({"type": "begin"})
    await client.act({"type": "hint"})
    assert client.state["turnsLeft"] == 13
    assert client.surfaces[-1][1] == {
        "id": "root",
        "component": "NarrationBlock",
        "title": "A word from your sergeant",
        "text": client.surfaces[-1][1]["text"],
        "tone": "neutral",
    }
    assert "the Guest Wing" in client.surfaces[-1][1]["text"]
