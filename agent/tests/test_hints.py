import pytest

from app.engine import clue_engine, hints
from app.engine.case_library import library
from app.engine.clue_engine import GameRuleError
from app.engine.solver import fresh_progress


def test_first_hint_points_at_the_first_missing_evidence(case, progress):
    text, outcome = hints.take_hint(case, progress)
    assert "about the Guest Wing" in text
    assert progress.turns_left == 13 and outcome.turns_spent == 2


def test_asking_again_about_the_same_step_is_explicit(case, progress):
    first, _ = hints.take_hint(case, progress)
    second, _ = hints.take_hint(case, progress)
    assert first != second
    assert second.startswith("Search the Guest Wing")


def test_hints_follow_progress(case, progress):
    clue_engine.examine(case, progress, "guest_wing")
    clue_engine.examine(case, progress, "study")
    assert hints.next_step(case, progress) == hints.Step("ask", suspect="s2", topic="garden")

    clue_engine.interrogate(case, progress, "s2", ["garden"])
    step = hints.next_step(case, progress)
    assert step == hints.Step("confront", suspect="s2", lie="s2_lie_garden", evidence="c3")
    assert "muddy shoes" in hints.hint_text(case, step, explicit=True)

    lie = next(s.id for s in progress.statements if s.lie_id == "s2_lie_garden")
    clue_engine.confront(case, progress, "s2", [lie, "c3"])
    assert hints.next_step(case, progress).kind == "accuse"


def test_never_spends_the_last_turns(case, progress):
    progress.turns_left = hints.HINT_COST
    with pytest.raises(GameRuleError):
        hints.take_hint(case, progress)
    assert progress.turns_left == hints.HINT_COST


def test_hints_never_assume_the_players_gender(case, progress):
    texts = []
    for _ in range(2):
        for kind in ("examine", "ask", "confront", "accuse"):
            step = {
                "examine": hints.Step("examine", location="study"),
                "ask": hints.Step("ask", suspect="s3", topic="garden"),
                "confront": hints.Step("confront", suspect="s2", lie="s2_lie_garden", evidence="c3"),
                "accuse": hints.Step("accuse"),
            }[kind]
            texts += [hints.hint_text(case, step, explicit=e) for e in (False, True)]
    assert not any(word in t.lower().split() for t in texts for word in ("sir", "madam", "ma'am", "man"))


@pytest.mark.parametrize("case_id", sorted(library()))
def test_following_only_the_sergeant_solves_every_case(case_id):
    """Each hint is actionable: doing exactly what it says always makes progress toward the solution."""
    case = library()[case_id]
    progress = fresh_progress(case, turns=999)
    for _ in range(30):
        step = hints.next_step(case, progress)
        if step.kind == "accuse":
            break
        if step.kind == "examine":
            clue_engine.examine(case, progress, step.location)
        elif step.kind == "ask":
            clue_engine.interrogate(case, progress, step.suspect, [step.topic])
        else:
            lie = next(s.id for s in progress.statements if s.lie_id == step.lie)
            assert clue_engine.confront(case, progress, step.suspect, [lie, step.evidence]).contradiction
    else:
        pytest.fail("hints never led to an accusation")
    assert set(case.solution.required_evidence) <= set(progress.revealed_clues)
    assert 999 - progress.turns_left <= case.max_turns  # a hint-follower still fits in a real game
