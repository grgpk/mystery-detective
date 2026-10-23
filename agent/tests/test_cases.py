"""Every case in the library must be solvable through the real rules engine within the turn budget."""

import pytest

from app.engine import clue_engine, scoring
from app.engine.case_library import catalogue, library, pick_case
from app.engine.validator import BUDGET_RATIO
from app.models.case import CaseFile, ConfrontUnlock, ExamineUnlock, InterrogateUnlock
from app.models.public import Accusation, Progress

CASES = sorted(library())


def reveal(case: CaseFile, progress: Progress, clue_id: str) -> None:
    """Plays the actions a sharp detective would need to turn up one clue."""
    if clue_id in progress.revealed_clues:
        return
    unlock = case.clue(clue_id).unlock
    if isinstance(unlock, ExamineUnlock):
        clue_engine.examine(case, progress, unlock.target)
    elif isinstance(unlock, InterrogateUnlock):
        clue_engine.interrogate(case, progress, unlock.suspect, [unlock.topic])
    else:
        assert isinstance(unlock, ConfrontUnlock)
        entry = next(c for c in case.contradictions if c.effect.reveals == clue_id)
        items = []
        for ref in (entry.a, entry.b):
            found = case.lie(ref)
            if found:
                suspect, lie = found
                clue_engine.interrogate(case, progress, suspect.id, lie.topics[:1])
                items.append(next(s.id for s in progress.statements if s.lie_id == ref))
            else:
                reveal(case, progress, ref)
                items.append(ref)
        assert clue_engine.confront(case, progress, entry.effect.suspect, items).contradiction
    assert clue_id in progress.revealed_clues


@pytest.mark.parametrize("case_id", CASES)
def test_case_is_solvable_within_budget(case_id):
    case = library()[case_id]
    progress = clue_engine.new_progress(case)
    progress.phase = "investigating"

    for clue_id in case.solution.required_evidence:
        reveal(case, progress, clue_id)

    turns_used = case.max_turns - progress.turns_left
    assert turns_used <= case.max_turns * BUDGET_RATIO
    accusation = Accusation(
        suspect_id=case.culprit,
        motive_id=case.solution.acceptable_motives[0],
        evidence=case.solution.required_evidence,
    )
    result = scoring.score(case, progress, accusation)
    assert result.culprit_correct and result.motive_correct
    assert result.valid_evidence == case.solution.required_evidence


@pytest.mark.parametrize("case_id", CASES)
def test_every_lie_can_be_told_and_broken(case_id):
    case = library()[case_id]
    for index, entry in enumerate(case.contradictions):
        progress = clue_engine.new_progress(case)
        progress.phase = "investigating"
        progress.turns_left = 99
        items = []
        for ref in (entry.a, entry.b):
            found = case.lie(ref)
            if found:
                suspect, lie = found
                clue_engine.interrogate(case, progress, suspect.id, lie.topics[:1])
                items.append(next(s.id for s in progress.statements if s.lie_id == ref))
            else:
                reveal(case, progress, ref)
                items.append(ref)
        outcome = clue_engine.confront(case, progress, entry.effect.suspect, items)
        assert outcome.contradiction == entry, f"contradiction #{index} could not be triggered"


def test_library_has_three_distinct_cases():
    cases = library().values()
    assert len(cases) >= 3
    assert len({c.setting.place for c in cases}) == len(cases)


def test_catalogue_is_spoiler_free():
    import json

    serialized = json.dumps(catalogue())
    for case in library().values():
        assert case.case_id in serialized
        assert case.motive.text not in serialized
        for suspect in case.suspects:
            assert suspect.name not in serialized


def test_unknown_case_id_falls_back_to_random():
    assert pick_case("no_such_case").case_id in library()
    assert pick_case("midnight_sleeper").case_id == "midnight_sleeper"
