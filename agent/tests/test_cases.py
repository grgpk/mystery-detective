"""Every case in the library must be solvable through the real rules engine within the turn budget."""

import json

import pytest

from app.engine import scoring, solver
from app.engine.case_library import catalogue, library, pick_case
from app.engine.validator import BUDGET_RATIO
from app.models.public import Accusation

CASES = sorted(library())


@pytest.mark.parametrize("case_id", CASES)
def test_case_is_solvable_within_budget(case_id):
    case = library()[case_id]
    progress = solver.solve(case)

    assert case.max_turns - progress.turns_left <= case.max_turns * BUDGET_RATIO
    accusation = Accusation(
        suspect_id=case.culprit,
        motive_id=case.solution.acceptable_motives[0],
        evidence=case.solution.required_evidence,
    )
    result = scoring.score(case, progress, accusation)
    assert result.culprit_correct and result.motive_correct
    assert result.valid_evidence == case.solution.required_evidence


@pytest.mark.parametrize("case_id", CASES)
def test_every_contradiction_can_be_triggered(case_id):
    case = library()[case_id]
    for index in range(len(case.contradictions)):
        solver.trigger_contradiction(case, index)


def test_library_has_three_distinct_cases():
    cases = library().values()
    assert len(cases) >= 3
    assert len({c.setting.place for c in cases}) == len(cases)


def test_catalogue_is_spoiler_free():
    serialized = json.dumps(catalogue())
    for case in library().values():
        assert case.case_id in serialized
        assert case.motive.text not in serialized
        for suspect in case.suspects:
            assert suspect.name not in serialized


def test_unknown_case_id_falls_back_to_random():
    assert pick_case("no_such_case").case_id in library()
    assert pick_case("midnight_sleeper").case_id == "midnight_sleeper"
