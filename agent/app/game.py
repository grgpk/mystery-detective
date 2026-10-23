"""Game master: turns one AG-UI run (one player action) into rule outcomes, dialogue, state and UI."""

import asyncio
import logging
from collections import defaultdict
from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Protocol

import anthropic
from ag_ui.core import BaseEvent, RunAgentInput
from pydantic import ValidationError

from app.a2ui import catalog
from app.agents import guards
from app.agents.classifier import classify_topics
from app.agents.extractor import extract_claim
from app.agents.narrator import JUDGE_SYSTEM, NARRATOR_SYSTEM, examine_prompt, judge_prompt
from app.agents.persona import persona_messages, persona_system_prompt, record_exchange, turn_context
from app.engine import clue_engine, hints, scoring
from app.engine.case_library import NEW_CASE_ID, pick_case
from app.engine.clue_engine import GameRuleError, Outcome
from app.engine.projection import project
from app.llm import JUDGE_MODEL, LLM, PERSONA_MODEL, LLMRefusal
from app.models.actions import (
    Accuse,
    Begin,
    Confront,
    Examine,
    GameAction,
    Hint,
    Interrogate,
    NewGame,
    OpenAccuse,
    OpenConfront,
    Start,
    SyncBoard,
    game_action_adapter,
)
from app.models.case import CaseFile
from app.models.public import Board, Progress, Statement
from app.protocol import agui
from app.store.repo import GameSession, SessionRepo

log = logging.getLogger(__name__)

MAX_NOTES = 4000
LLM_ERRORS = (anthropic.APIError, LLMRefusal)


class SessionOwnershipError(Exception):
    pass


class FreshCases(Protocol):
    """Source of newly generated, validated cases (the background pool)."""

    async def take(self) -> CaseFile | None: ...
    async def release(self, case: CaseFile) -> None: ...


# A generated case opened but never begun has given nothing away (the briefing is spoiler-free), so it goes back.
ABANDONED_BRIEFING = timedelta(hours=1)
NO_FRESH_CASE = "No freshly written case is ready yet, so here is one from the archive."


def parse_action(forwarded_props: object) -> GameAction:
    raw = (forwarded_props or {}).get("gameAction") if isinstance(forwarded_props, dict) else None
    if raw is None:
        return Start(type="start")
    try:
        return game_action_adapter.validate_python(raw)
    except ValidationError as exc:
        raise GameRuleError("I didn't understand that request.") from exc


def sanitize_board(board: Board, progress: Progress) -> Board:
    """The board is player-written; keep only references to things they have actually found."""
    visible = clue_engine.visible_ids(progress)
    pins = [p for p in dict.fromkeys(board.pins) if p in visible]
    links = [link for link in board.links if link.from_ in visible and link.to in visible and link.from_ != link.to]
    return Board(pins=pins, links=links[:100], notes=board.notes[:MAX_NOTES])


class Turn:
    """One run: holds the session and tracks what public state the client has seen."""

    def __init__(self, session: GameSession, client_state: dict | None):
        self.session = session
        self.sent = project(session.case, session.progress).dump()
        self.needs_snapshot = not client_state or client_state.get("caseId") != session.case.case_id

    @property
    def case(self) -> CaseFile:
        return self.session.case

    @property
    def progress(self) -> Progress:
        return self.session.progress

    def sync_state(self) -> list[BaseEvent]:
        current = project(self.case, self.progress).dump()
        if self.needs_snapshot:
            self.needs_snapshot = False
            self.sent = current
            return [agui.state_snapshot(current)]
        delta = agui.state_delta(self.sent, current)
        self.sent = current
        return [delta] if delta else []

    def surface(self, kind: str, components: list[dict]) -> list[BaseEvent]:
        self.progress.ui_seq += 1
        return agui.a2ui_surface(f"{kind}-{self.progress.ui_seq}", components)


class GameMaster:
    def __init__(self, llm: LLM, repo: SessionRepo, fresh_cases: FreshCases | None = None):
        self.llm = llm
        self.repo = repo
        self.fresh_cases = fresh_cases
        self._locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def run(self, run_input: RunAgentInput, owner: str) -> AsyncIterator[BaseEvent]:
        thread_id, run_id = run_input.thread_id, run_input.run_id
        yield agui.run_started(thread_id, run_id)
        try:
            async with self._locks[thread_id]:
                async for event in self._run_locked(run_input, owner):
                    yield event
        except SessionOwnershipError:
            yield agui.run_error("This case belongs to another session.", code="forbidden")
            return
        except Exception:
            log.exception("run failed")
            yield agui.run_error("The game master lost the thread. Please try again.")
            return
        yield agui.run_finished(thread_id, run_id)

    async def _run_locked(self, run_input: RunAgentInput, owner: str) -> AsyncIterator[BaseEvent]:
        thread_id = run_input.thread_id
        session = await self.repo.get(thread_id)
        if session and session.owner != owner:
            raise SessionOwnershipError

        try:
            action = parse_action(run_input.forwarded_props)
        except GameRuleError as err:
            async for event in agui.text_message("narrator", str(err)):
                yield event
            return

        fresh = session is None or isinstance(action, NewGame)
        notice = None
        if fresh:
            await self._return_unstarted(owner=owner)
            case, notice = await self._choose_case(getattr(action, "case_id", None))
            session = GameSession(thread_id, owner, case, clue_engine.new_progress(case))

        client_state = run_input.state if isinstance(run_input.state, dict) else None
        board_drift = False
        if client_state and not fresh and isinstance(client_state.get("board"), dict):
            try:
                session.progress.board = sanitize_board(Board.model_validate(client_state["board"]), session.progress)
                board_drift = session.progress.board.dump() != client_state["board"]
            except ValidationError:
                board_drift = True

        turn = Turn(session, None if fresh else client_state)
        if isinstance(action, (Start, NewGame)) or board_drift:
            # Deltas assume the client holds exactly what we last sent; resync when it doesn't.
            turn.needs_snapshot = True
        clue_engine.begin_turn(session.progress)

        try:
            if notice:
                async for event in agui.text_message("narrator", notice):
                    yield event
            async for event in self._dispatch(turn, action, fresh):
                yield event
        except GameRuleError as err:
            async for event in agui.text_message("narrator", str(err)):
                yield event

        for event in turn.sync_state():
            yield event
        await self.repo.save(session)

    async def _choose_case(self, requested: str | None) -> tuple[CaseFile, str | None]:
        if requested != NEW_CASE_ID:
            return pick_case(requested), None
        await self._return_unstarted(idle_for=ABANDONED_BRIEFING)  # tabs closed on the briefing
        if self.fresh_cases and (case := await self.fresh_cases.take()):
            return case, None
        return pick_case(None), NO_FRESH_CASE

    async def _return_unstarted(self, owner: str | None = None, idle_for: timedelta | None = None) -> None:
        """Returns generated cases from games that never got past the briefing to the pool."""
        if self.fresh_cases is None:
            return
        for abandoned in await self.repo.unstarted_generated(owner=owner, idle_for=idle_for):
            await self.repo.delete(abandoned.thread_id)
            await self.fresh_cases.release(abandoned.case)
            log.info("returned unstarted case %s to the pool", abandoned.case.case_id)

    async def _dispatch(self, turn: Turn, action: GameAction, fresh: bool) -> AsyncIterator[BaseEvent]:
        match action:
            case Start() | NewGame():
                handler = self._start(turn, fresh)
            case Begin():
                handler = self._begin(turn)
            case Interrogate():
                handler = self._interrogate(turn, action)
            case Examine():
                handler = self._examine(turn, action)
            case Hint():
                handler = self._hint(turn)
            case OpenConfront():
                handler = self._open_confront(turn, action)
            case Confront():
                handler = self._confront(turn, action)
            case OpenAccuse():
                handler = self._open_accuse(turn)
            case Accuse():
                handler = self._accuse(turn, action)
            case SyncBoard():
                turn.progress.board = sanitize_board(action.board, turn.progress)
                return
        async for event in handler:
            yield event

    # ---- handlers -----------------------------------------------------------

    async def _start(self, turn: Turn, fresh: bool) -> AsyncIterator[BaseEvent]:
        for event in turn.sync_state():
            yield event
        phase = turn.progress.phase
        if phase == "briefing":
            for event in turn.surface("briefing", [catalog.case_briefing()]):
                yield event
            return
        for event in self._board_surfaces(turn):
            yield event
        if phase == "accusing":
            for event in turn.surface("accuse", [catalog.accusation_form()]):
                yield event
        elif phase == "ended":
            for event in turn.surface("verdict", [catalog.verdict_screen()]):
                yield event

    def _board_surfaces(self, turn: Turn) -> list[BaseEvent]:
        return [
            *turn.surface("roster", catalog.roster([s.id for s in turn.case.suspects])),
            *turn.surface("map", catalog.map_panel([loc.id for loc in turn.case.setting.locations])),
        ]

    async def _begin(self, turn: Turn) -> AsyncIterator[BaseEvent]:
        if turn.progress.phase != "briefing":
            return
        turn.progress.phase = "investigating"
        for event in turn.sync_state():
            yield event
        for event in self._board_surfaces(turn):
            yield event
        text = (
            f"You have {turn.progress.turns_left} turns before the Chief Constable arrives. Question the household, "
            "search the rooms, and catch a liar out with proof."
        )
        for event in turn.surface("narration", [catalog.narration(text, title="The investigation begins")]):
            yield event

    def _ensure_started(self, turn: Turn) -> None:
        if turn.progress.phase == "briefing":
            turn.progress.phase = "investigating"

    async def _interrogate(self, turn: Turn, action: Interrogate) -> AsyncIterator[BaseEvent]:
        self._ensure_started(turn)
        case, progress = turn.case, turn.progress
        clue_engine.known_suspect(case, action.suspect_id)
        topics = await classify_topics(self.llm, case, action.question)
        outcome = clue_engine.interrogate(case, progress, action.suspect_id, topics)

        context = turn_context(case, progress, action.suspect_id, outcome.allowed_reveals, outcome.new_statements)
        reply_parts: list[str] = []
        async for event in self._persona_reply(turn, action.suspect_id, action.question, context, outcome, reply_parts):
            yield event
        reply = "".join(reply_parts)
        record_exchange(progress, action.suspect_id, action.question, reply)
        await self._record_testimony(turn, action.suspect_id, reply, outcome)

        async for event in self._after_outcome(turn, outcome):
            yield event

    async def _examine(self, turn: Turn, action: Examine) -> AsyncIterator[BaseEvent]:
        self._ensure_started(turn)
        case = turn.case
        outcome = clue_engine.examine(case, turn.progress, action.location_id)
        prompt = examine_prompt(case, action.location_id, outcome.new_clues)
        async for event in self._narrate(NARRATOR_SYSTEM, prompt, PERSONA_MODEL, max_tokens=400):
            yield event
        if not outcome.new_clues:
            async for event in agui.text_message("narrator", "Nothing here seems to bear on the case."):
                yield event
        async for event in self._after_outcome(turn, outcome):
            yield event

    async def _hint(self, turn: Turn) -> AsyncIterator[BaseEvent]:
        self._ensure_started(turn)
        text, outcome = hints.take_hint(turn.case, turn.progress)
        for event in turn.sync_state():
            yield event
        for event in turn.surface("narration", [catalog.narration(text, title="A word from your sergeant")]):
            yield event
        async for event in self._after_outcome(turn, outcome):
            yield event

    async def _open_confront(self, turn: Turn, action: OpenConfront) -> AsyncIterator[BaseEvent]:
        self._ensure_started(turn)
        clue_engine.known_suspect(turn.case, action.suspect_id)
        if not turn.progress.statements:
            raise GameRuleError("You have no statements to confront anyone with yet. Question someone first.")
        for event in turn.surface("confront", [catalog.confront_picker(action.suspect_id)]):
            yield event

    async def _confront(self, turn: Turn, action: Confront) -> AsyncIterator[BaseEvent]:
        self._ensure_started(turn)
        case, progress = turn.case, turn.progress
        outcome = clue_engine.confront(case, progress, action.suspect_id, action.items)
        suspect = case.suspect(action.suspect_id)

        if outcome.contradiction:
            for event in turn.sync_state():  # composure drop + red string before the reaction
                yield event
            banner = catalog.narration(
                f"{suspect.name}'s story does not hold up.", title="Contradiction!", tone="alert"
            )
            for event in turn.surface("narration", [banner]):
                yield event

        presented = [self._describe_item(turn, item) for item in action.items]
        context = turn_context(
            case,
            progress,
            action.suspect_id,
            outcome.allowed_reveals,
            [s for s in outcome.new_statements if s.kind != "confession"],
            confrontation=(presented, outcome.contradiction),
        )
        detective = "Explain this, if you can: " + " / ".join(presented)
        reply_parts: list[str] = []
        async for event in self._persona_reply(turn, action.suspect_id, detective, context, outcome, reply_parts):
            yield event
        record_exchange(progress, action.suspect_id, detective, "".join(reply_parts))

        if not outcome.contradiction:
            async for event in agui.text_message("narrator", "That proves nothing. The turn is spent."):
                yield event
        async for event in self._after_outcome(turn, outcome):
            yield event

    async def _open_accuse(self, turn: Turn) -> AsyncIterator[BaseEvent]:
        if turn.progress.phase == "ended":
            raise GameRuleError("The case is already closed.")
        for event in turn.surface("accuse", [catalog.accusation_form()]):
            yield event

    async def _accuse(self, turn: Turn, action: Accuse) -> AsyncIterator[BaseEvent]:
        case, progress = turn.case, turn.progress
        if progress.phase == "ended":
            raise GameRuleError("The case is already closed.")
        accusation = action.accusation
        clue_engine.known_suspect(case, accusation.suspect_id)
        if accusation.motive_id not in {m.id for m in case.motive_options}:
            raise GameRuleError("Choose one of the motives on the form.")
        if any(e not in progress.revealed_clues for e in accusation.evidence):
            raise GameRuleError("You can only cite evidence you have actually found.")

        progress.accusation = accusation
        progress.score = scoring.score(case, progress, accusation)
        progress.phase = "ended"
        progress.conversation = None
        for event in turn.sync_state():
            yield event
        for event in turn.surface("verdict", [catalog.verdict_screen()]):
            yield event
        prompt = judge_prompt(case, progress, accusation, progress.score)
        async for event in self._narrate(JUDGE_SYSTEM, prompt, JUDGE_MODEL, max_tokens=2000, effort="medium"):
            yield event

    # ---- helpers --------------------------------------------------------------

    async def _after_outcome(self, turn: Turn, outcome: Outcome) -> AsyncIterator[BaseEvent]:
        """State first, then UI that refers to it (so cards never render an unknown id)."""
        for event in turn.sync_state():
            yield event
        if outcome.new_clues:
            for event in turn.surface("clue", catalog.clue_cards(outcome.new_clues)):
                yield event
        if turn.progress.phase == "accusing":
            text = "Your time is up. The Chief Constable is at the door. Name the killer."
            for event in turn.surface("narration", [catalog.narration(text, title="Time's up", tone="alert")]):
                yield event
            for event in turn.surface("accuse", [catalog.accusation_form()]):
                yield event

    def _describe_item(self, turn: Turn, item_id: str) -> str:
        if item_id in turn.progress.revealed_clues:
            return f"the {turn.case.clue(item_id).title.lower()}"
        statement = next(s for s in turn.progress.statements if s.id == item_id)
        speaker = turn.case.suspect(statement.suspect).name
        return f'{speaker} said "{statement.text}"'

    async def _record_testimony(self, turn: Turn, suspect_id: str, reply: str, outcome: Outcome) -> None:
        progress = turn.progress
        recorded = [s.text for s in progress.statements if s.suspect == suspect_id]
        try:
            claim = await extract_claim(self.llm, turn.case.suspect(suspect_id).name, reply, recorded)
        except LLM_ERRORS:
            log.warning("statement extraction failed", exc_info=True)
            return
        if claim:
            statement = Statement(
                id=f"st{len(progress.statements) + 1}", suspect=suspect_id, text=claim, kind="testimony"
            )
            progress.statements.append(statement)
            outcome.new_statements.append(statement)

    async def _persona_reply(
        self,
        turn: Turn,
        suspect_id: str,
        detective_text: str,
        context: str,
        outcome: Outcome,
        reply_parts: list[str],
    ) -> AsyncIterator[BaseEvent]:
        """Streams a suspect's reply sentence by sentence through the leak guard."""
        case, progress = turn.case, turn.progress
        protected = guards.protected_texts(case, progress, suspect_id, outcome.allowed_reveals)
        name = case.suspect(suspect_id).name
        stream = agui.TextStream(suspect_id)
        yield stream.start()
        buffer, blocked = "", False
        try:
            async for delta in self.llm.stream(
                model=PERSONA_MODEL,
                system=persona_system_prompt(case, suspect_id),
                messages=persona_messages(progress, suspect_id, detective_text, context),
                max_tokens=600,
            ):
                buffer += delta
                sentences, buffer = guards.split_complete_sentences(buffer)
                for sentence in sentences:
                    if guards.leaks(sentence, protected):
                        blocked = True
                        break
                    if spoken := guards.clean_speech(sentence, name, first=not reply_parts):
                        reply_parts.append(spoken)
                        yield stream.chunk(spoken)
                if blocked:
                    break
            if not blocked and buffer.strip():
                if guards.leaks(buffer, protected):
                    blocked = True
                elif spoken := guards.clean_speech(buffer, name, first=not reply_parts):
                    reply_parts.append(spoken)
                    yield stream.chunk(spoken)
        except LLM_ERRORS:
            log.warning("persona call failed", exc_info=True)
            blocked = True
        if blocked or not reply_parts:
            # Rules already decided what this suspect says; fall back to those lines if the model can't.
            must_say = " ".join(st.text for st in outcome.new_statements)
            fallback = guards.DEFLECTION if reply_parts or not must_say else must_say
            reply_parts.append(fallback)
            yield stream.chunk(fallback)
        yield stream.end()

    async def _narrate(
        self, system: str, prompt: str, model: str, max_tokens: int, effort: str = "low"
    ) -> AsyncIterator[BaseEvent]:
        stream = agui.TextStream("narrator")
        yield stream.start()
        try:
            async for delta in self.llm.stream(
                model=model,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                effort=effort,
            ):
                # Prose only: models sometimes add markdown emphasis, which would show literally.
                if text := delta.replace("*", "").replace("_", ""):
                    yield stream.chunk(text)
        except LLM_ERRORS:
            log.warning("narration failed", exc_info=True)
            yield stream.chunk("The fog thickens; the narrator falls silent.")
        yield stream.end()
