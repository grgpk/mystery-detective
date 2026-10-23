"""Deterministic game rules: turns, unlocks, statements, contradictions, composure.

Nothing in here calls an LLM. The LLM only ever narrates outcomes decided here.
"""

from dataclasses import dataclass, field

from app.models.case import CaseFile, Contradiction, ExamineUnlock, InterrogateUnlock
from app.models.public import BoardLink, Conversation, Progress, Statement

QUESTIONS_PER_TURN = 3
IMPLICIT_FIRST_TOPIC = "whereabouts"


class GameRuleError(Exception):
    """A player action that the rules reject (shown to the player, never a crash)."""


@dataclass
class Outcome:
    turns_spent: int = 0
    new_clues: list[str] = field(default_factory=list)
    new_statements: list[Statement] = field(default_factory=list)
    revealed_secrets: list[str] = field(default_factory=list)
    contradiction: Contradiction | None = None
    composure_delta: int = 0

    @property
    def allowed_reveals(self) -> list[str]:
        """Facts the persona may voice this turn: newly unlocked clues and secrets."""
        return [*self.new_clues, *self.revealed_secrets]


def new_progress(case: CaseFile) -> Progress:
    return Progress(
        turns_left=case.max_turns,
        composure={s.id: s.starting_composure for s in case.suspects},
    )


def mood_for(composure: int) -> str:
    if composure >= 80:
        return "calm"
    if composure >= 50:
        return "guarded"
    if composure >= 25:
        return "nervous"
    return "cracking"


def require_investigating(progress: Progress) -> None:
    if progress.phase == "ended":
        raise GameRuleError("The case is closed.")
    if progress.phase == "accusing" or progress.turns_left <= 0:
        raise GameRuleError("You are out of turns. It is time to name the killer.")


def spend(progress: Progress, outcome: Outcome, turns: int = 1) -> None:
    progress.turns_left = max(0, progress.turns_left - turns)
    outcome.turns_spent += turns
    if progress.turns_left == 0:
        progress.phase = "accusing"


def _reveal_clue(progress: Progress, outcome: Outcome, clue_id: str) -> None:
    if clue_id not in progress.revealed_clues:
        progress.revealed_clues.append(clue_id)
        progress.new_clues.append(clue_id)
        outcome.new_clues.append(clue_id)


def _add_statement(progress: Progress, outcome: Outcome, **fields) -> Statement:
    statement = Statement(id=f"st{len(progress.statements) + 1}", **fields)
    progress.statements.append(statement)
    outcome.new_statements.append(statement)
    return statement


def _check_secrets(case: CaseFile, progress: Progress, outcome: Outcome, suspect_id: str) -> None:
    composure = progress.composure[suspect_id]
    for secret in case.suspect(suspect_id).secrets:
        if secret.id in progress.revealed_secrets or composure > secret.reveal_at_composure:
            continue
        progress.revealed_secrets.append(secret.id)
        outcome.revealed_secrets.append(secret.id)
        _add_statement(progress, outcome, suspect=suspect_id, text=secret.confession, kind="confession")


def begin_turn(progress: Progress) -> None:
    """Clears per-turn highlights before any new action is applied."""
    progress.new_clues = []
    progress.last_contradiction = None


def known_suspect(case: CaseFile, suspect_id: str) -> None:
    if suspect_id not in {s.id for s in case.suspects}:
        raise GameRuleError("There is nobody by that name in the house.")


def interrogate(case: CaseFile, progress: Progress, suspect_id: str, topics: list[str]) -> Outcome:
    """One question to a suspect. A turn buys up to three questions to the same suspect."""
    require_investigating(progress)
    known_suspect(case, suspect_id)
    outcome = Outcome()

    conv = progress.conversation
    if conv is None or conv.suspect_id != suspect_id or conv.questions_left <= 0:
        spend(progress, outcome)
        conv = Conversation(suspect_id=suspect_id, questions_left=QUESTIONS_PER_TURN)
    conv.questions_left -= 1
    progress.conversation = conv

    first_time = suspect_id not in progress.interrogated
    if first_time:
        progress.interrogated.append(suspect_id)
        topics = [IMPLICIT_FIRST_TOPIC, *topics]

    asked = progress.asked_topics.setdefault(suspect_id, [])
    for topic in topics:
        if topic not in asked:
            asked.append(topic)

    suspect = case.suspect(suspect_id)
    stated_lies = {s.lie_id for s in progress.statements if s.lie_id}
    for lie in suspect.lies:
        if lie.id not in stated_lies and set(lie.topics) & set(topics):
            kind = "alibi" if IMPLICIT_FIRST_TOPIC in lie.topics else "claim"
            _add_statement(progress, outcome, suspect=suspect_id, text=lie.statement, kind=kind, lie_id=lie.id)

    if first_time and not any(IMPLICIT_FIRST_TOPIC in lie.topics for lie in suspect.lies):
        _add_statement(progress, outcome, suspect=suspect_id, text=suspect.alibi_claim, kind="alibi")

    for clue in case.clues:
        unlock = clue.unlock
        if isinstance(unlock, InterrogateUnlock) and unlock.suspect == suspect_id and unlock.topic in topics:
            _reveal_clue(progress, outcome, clue.id)

    return outcome


def examine(case: CaseFile, progress: Progress, location_id: str) -> Outcome:
    require_investigating(progress)
    if location_id not in case.location_ids():
        raise GameRuleError("There is no such place in the house.")
    if location_id in progress.examined_locations:
        raise GameRuleError("You have already searched there thoroughly.")
    outcome = Outcome()
    spend(progress, outcome)
    progress.conversation = None
    progress.examined_locations.append(location_id)
    for clue in case.clues:
        if isinstance(clue.unlock, ExamineUnlock) and clue.unlock.target == location_id:
            _reveal_clue(progress, outcome, clue.id)
    return outcome


def _resolve_item(case: CaseFile, progress: Progress, item_id: str) -> set[str]:
    """Maps a confront item (revealed clue or recorded statement) to the case ids it stands for."""
    if item_id in progress.revealed_clues:
        return {item_id}
    statement = next((s for s in progress.statements if s.id == item_id), None)
    if statement is None:
        raise GameRuleError("You can only present evidence you have actually found.")
    return {item_id, statement.lie_id} if statement.lie_id else {item_id}


def confront(case: CaseFile, progress: Progress, suspect_id: str, items: list[str]) -> Outcome:
    require_investigating(progress)
    known_suspect(case, suspect_id)
    if len(items) != 2 or items[0] == items[1]:
        raise GameRuleError("Choose exactly two different pieces: a statement and the evidence that contradicts it.")
    left, right = (_resolve_item(case, progress, i) for i in items)

    outcome = Outcome()
    spend(progress, outcome)
    progress.conversation = None

    for index, entry in enumerate(case.contradictions):
        if index in progress.contradictions_found or entry.effect.suspect != suspect_id:
            continue
        if (entry.a in left and entry.b in right) or (entry.a in right and entry.b in left):
            progress.contradictions_found.append(index)
            outcome.contradiction = entry
            outcome.composure_delta = entry.effect.composure
            progress.composure[suspect_id] = max(0, progress.composure[suspect_id] + entry.effect.composure)
            progress.last_contradiction = BoardLink(from_=items[0], to=items[1])
            if entry.effect.reveals:
                _reveal_clue(progress, outcome, entry.effect.reveals)
            _check_secrets(case, progress, outcome, suspect_id)
            break

    return outcome


def visible_ids(progress: Progress) -> set[str]:
    return {*progress.revealed_clues, *(s.id for s in progress.statements)}
