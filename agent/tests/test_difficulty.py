import uuid

import pytest
from ag_ui.core import RunAgentInput

from app.engine import clue_engine, difficulty, hints, scoring
from app.engine.case_library import DAILY_CASE_ID, library
from app.game import GameMaster
from app.llm import ScriptedLLM
from app.models.public import Accusation
from app.store.repo import InMemoryRepo


def test_budgets(case):
    assert [clue_engine.new_progress(case, lvl).turns_left for lvl in ("easy", "normal", "hard")] == [20, 15, 11]


@pytest.mark.parametrize(("level", "expected"), [("easy", 61), ("normal", 70), ("hard", 78)])
def test_suspects_crack_faster_on_easy(case, level, expected):
    progress = clue_engine.new_progress(case, level)
    progress.phase = "investigating"
    clue_engine.interrogate(case, progress, "s2", ["garden"])
    clue_engine.examine(case, progress, "guest_wing")
    lie = next(s.id for s in progress.statements if s.lie_id == "s2_lie_garden")
    clue_engine.confront(case, progress, "s2", [lie, "c3"])  # a -30 contradiction
    assert progress.composure["s2"] == expected


def test_easy_cannot_outscore_normal_on_spare_turns(case):
    accusation = Accusation(suspect_id="s2", motive_id="inheritance")
    easy, normal = clue_engine.new_progress(case, "easy"), clue_engine.new_progress(case, "normal")
    easy.turns_left, normal.turns_left = 17, 12  # both used 3 turns
    assert scoring.score(case, easy, accusation).turn_points == 10
    easy.turns_left = 12  # used 8 turns: 7 spare beyond Easy's bonus
    assert scoring.score(case, easy, accusation).turn_points == 7
    assert scoring.score(case, normal, accusation).turn_points == 10


@pytest.mark.parametrize(("level", "cost"), [("easy", 1), ("normal", 2), ("hard", 3)])
def test_hint_cost(case, level, cost):
    progress = clue_engine.new_progress(case, level)
    progress.phase = "investigating"
    before = progress.turns_left
    hints.take_hint(case, progress)
    assert before - progress.turns_left == cost
    progress.turns_left = cost
    with pytest.raises(clue_engine.GameRuleError):
        hints.take_hint(case, progress)


def test_saved_games_from_before_levels_still_load(case):
    progress = clue_engine.new_progress(case)
    progress.max_turns = None  # as stored before difficulty existed
    assert clue_engine.max_turns(case, progress) == case.max_turns


@pytest.mark.parametrize("case_id", sorted(library()))
def test_every_case_is_winnable_on_hard_by_following_hints(case_id):
    """The shortest route to the evidence (what the hints point along) fits in Hard's 11 turns for every case.

    Buying a hint at every step would not fit at 3 turns each; Hard is meant to make hints a real cost.
    """
    case = library()[case_id]
    progress = clue_engine.new_progress(case, "hard")
    progress.phase = "investigating"
    for _ in range(20):
        step = hints.next_step(case, progress)
        if step.kind == "accuse":
            break
        if step.kind == "examine":
            clue_engine.examine(case, progress, step.location)
        elif step.kind == "ask":
            clue_engine.interrogate(case, progress, step.suspect, [step.topic])
        else:
            lie = next(s.id for s in progress.statements if s.lie_id == step.lie)
            clue_engine.confront(case, progress, step.suspect, [lie, step.evidence])
    assert progress.phase == "investigating" and progress.turns_left >= 1, case_id
    assert set(case.solution.required_evidence) <= set(progress.revealed_clues)


async def start(game, action) -> dict:
    run_input = RunAgentInput(
        thread_id=uuid.uuid4().hex,
        run_id="r",
        state={},
        messages=[],
        tools=[],
        context=[],
        forwarded_props={"gameAction": action},
    )
    events = [e async for e in game.run(run_input, f"p-{uuid.uuid4().hex[:6]}")]
    return next(e.snapshot for e in events if e.type == "STATE_SNAPSHOT")


async def test_new_game_at_a_difficulty():
    state = await start(GameMaster(ScriptedLLM(), InMemoryRepo()), {"type": "start", "difficulty": "hard"})
    assert (state["difficulty"], state["maxTurns"], state["turnsLeft"], state["hintCost"]) == ("hard", 11, 11, 3)


async def test_daily_case_is_always_normal():
    state = await start(
        GameMaster(ScriptedLLM(), InMemoryRepo()), {"type": "start", "caseId": DAILY_CASE_ID, "difficulty": "easy"}
    )
    assert state["difficulty"] == difficulty.DEFAULT and state["maxTurns"] == 15
