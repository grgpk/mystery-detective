"""Launch hardening: analytics, per-player limits, and the agent's shared secret."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException

from app import main
from app.analytics import GameRecord, summarize
from app.engine import clue_engine, scoring
from app.engine.case_library import NEW_CASE_ID, library
from app.game import FRESH_LIMIT, GameMaster, Limits
from app.generation.pool import InMemoryCasePool, PoolFiller
from app.llm import ScriptedLLM
from app.models.public import Accusation
from app.store.repo import InMemoryRepo
from tests.test_generation import scripted, start_new_case, valid_generated

NOW = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)


def record(phase: str, *, culprit: str | None = None, age: timedelta = timedelta(minutes=5), **progress) -> GameRecord:
    case = library()["ashford_manor"]
    p = clue_engine.new_progress(case)
    p.phase = phase
    for key, value in progress.items():
        setattr(p, key, value)
    if culprit:
        p.score = scoring.score(case, p, Accusation(suspect_id=culprit, motive_id="inheritance"))
    return GameRecord(case, p, created_at=NOW - age - timedelta(minutes=20), updated_at=NOW - age)


def test_summary_metrics_and_targets():
    records = [
        record("briefing"),  # opened, never begun: excluded from rates
        record("ended", culprit="s2", turns_left=6, hints=["x"]),
        record("ended", culprit="s2", turns_left=8),
        record("ended", culprit="s4", turns_left=0),
        record("investigating", age=timedelta(hours=3), examined_locations=["study"]),  # abandoned
    ]
    stats = summarize(records, NOW)
    assert stats["games"] == {"opened": 5, "begun": 4, "accused": 3, "solved": 2, "abandoned": 1}
    assert stats["metrics"] == {"accusation_rate": 0.75, "solve_rate": 0.667}
    assert stats["targets"]["accusation_rate"]["met"] is True
    assert stats["targets"]["solve_rate"]["met"] is True
    assert stats["accused_games"]["avg_turns_used"] == round((9 + 7 + 15) / 3, 1)
    assert stats["stalls"] == {"never questioned anyone": 1}
    assert stats["cases"][0]["caseId"] == "ashford_manor" and stats["cases"][0]["solveRate"] == 0.667


def test_summary_of_nothing():
    stats = summarize([], NOW)
    assert stats["metrics"] == {"accusation_rate": None, "solve_rate": None}
    assert stats["targets"]["solve_rate"]["met"] is None


async def test_daily_game_cap():
    game = GameMaster(ScriptedLLM(), InMemoryRepo(), limits=Limits(games_per_day=1))
    await start_new_case(game, action={"type": "start", "caseId": "ashford_manor"})
    run = [e async for e in game.run(_input("t-2"), "player")]
    errors = [e for e in run if e.type == "RUN_ERROR"]
    assert errors and errors[0].code == "limit" and "tomorrow" in errors[0].message


async def test_fresh_case_cap_falls_back_to_the_archive():
    filler = PoolFiller(InMemoryCasePool(), scripted(valid_generated()), target=1)
    await filler.fill_once()
    game = GameMaster(ScriptedLLM(), InMemoryRepo(), fresh_cases=filler, limits=Limits(fresh_cases_per_day=0))
    snapshot, texts = await start_new_case(game)
    assert snapshot["caseId"] in library()
    assert FRESH_LIMIT in texts
    assert await filler.pool.ready() == 1  # the generated case was not spent


def test_shared_secret(monkeypatch):
    monkeypatch.setattr(main, "AGENT_SHARED_SECRET", "s3cret")
    main.require_agent_key("s3cret")
    for wrong in (None, "", "guess"):
        with pytest.raises(HTTPException) as exc:
            main.require_agent_key(wrong)
        assert exc.value.status_code == 403
    monkeypatch.setattr(main, "AGENT_SHARED_SECRET", "")
    main.require_agent_key(None)  # unset: local dev stays open


def _input(thread_id: str):
    from ag_ui.core import RunAgentInput

    return RunAgentInput(
        thread_id=thread_id,
        run_id="r",
        state={},
        messages=[],
        tools=[],
        context=[],
        forwarded_props={"gameAction": {"type": "start", "caseId": NEW_CASE_ID}},
    )
