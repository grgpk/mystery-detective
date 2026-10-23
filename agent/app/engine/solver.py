"""Plays a case through the real rules engine, the way a sharp detective would.

Used by the validator to prove a case is solvable (not just plausibly so), and by tests.
"""

from app.engine import clue_engine
from app.engine.clue_engine import GameRuleError
from app.models.case import CaseFile, Contradiction, ExamineUnlock, InterrogateUnlock
from app.models.public import Progress


class Unsolvable(Exception):
    pass


def fresh_progress(case: CaseFile, turns: int | None = None) -> Progress:
    progress = clue_engine.new_progress(case)
    progress.phase = "investigating"
    if turns is not None:
        progress.turns_left = turns
    return progress


def _statement_for_lie(case: CaseFile, progress: Progress, lie_id: str) -> str:
    found = case.lie(lie_id)
    if found is None:
        raise Unsolvable(f"unknown lie {lie_id}")
    suspect, lie = found
    if not any(s.lie_id == lie_id for s in progress.statements):
        clue_engine.interrogate(case, progress, suspect.id, lie.topics[:1])
    statement = next((s.id for s in progress.statements if s.lie_id == lie_id), None)
    if statement is None:
        raise Unsolvable(f"lie {lie_id} is never told when asked about {lie.topics[:1]}")
    return statement


def _confront_items(case: CaseFile, progress: Progress, entry: Contradiction, depth: int) -> list[str]:
    items = []
    for ref in (entry.a, entry.b):
        if case.lie(ref):
            items.append(_statement_for_lie(case, progress, ref))
        else:
            reveal(case, progress, ref, depth + 1)
            items.append(ref)
    return items


def reveal(case: CaseFile, progress: Progress, clue_id: str, depth: int = 0) -> None:
    """Takes the actions needed to turn up one clue, or raises Unsolvable."""
    if clue_id in progress.revealed_clues:
        return
    if depth > 6:
        raise Unsolvable(f"clue {clue_id} depends on itself")
    clue = next((c for c in case.clues if c.id == clue_id), None)
    if clue is None:
        raise Unsolvable(f"unknown clue {clue_id}")
    try:
        if isinstance(clue.unlock, ExamineUnlock):
            clue_engine.examine(case, progress, clue.unlock.target)
        elif isinstance(clue.unlock, InterrogateUnlock):
            clue_engine.interrogate(case, progress, clue.unlock.suspect, [clue.unlock.topic])
        else:
            entry = next((c for c in case.contradictions if c.effect.reveals == clue_id), None)
            if entry is None:
                raise Unsolvable(f"confront-only clue {clue_id} is never revealed")
            items = _confront_items(case, progress, entry, depth)
            if not clue_engine.confront(case, progress, entry.effect.suspect, items).contradiction:
                raise Unsolvable(f"contradiction revealing {clue_id} does not fire")
    except GameRuleError as err:
        raise Unsolvable(f"while revealing {clue_id}: {err}") from err
    if clue_id not in progress.revealed_clues:
        raise Unsolvable(f"clue {clue_id} did not appear")


def solve(case: CaseFile) -> Progress:
    """Reveals all required evidence with a full turn budget; returns the final progress."""
    progress = fresh_progress(case)
    for clue_id in case.solution.required_evidence:
        reveal(case, progress, clue_id)
    return progress


def trigger_contradiction(case: CaseFile, index: int) -> None:
    """Proves one contradiction can actually be set off by a player (unlimited turns)."""
    entry = case.contradictions[index]
    progress = fresh_progress(case, turns=999)
    try:
        items = _confront_items(case, progress, entry, depth=0)
        outcome = clue_engine.confront(case, progress, entry.effect.suspect, items)
    except GameRuleError as err:
        raise Unsolvable(f"contradiction {entry.a}/{entry.b}: {err}") from err
    if outcome.contradiction != entry:
        raise Unsolvable(f"contradiction {entry.a}/{entry.b} cannot be triggered")
