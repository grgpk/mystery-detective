from datetime import UTC, date, datetime, timedelta

from app import career
from app.analytics import GameRecord
from app.engine import clue_engine, scoring
from app.engine.case_library import library
from app.game import GameMaster
from app.llm import ScriptedLLM
from app.models.public import Accusation
from app.store.repo import InMemoryRepo
from tests.test_daily import run, snapshot

TODAY = date(2026, 10, 23)


def closed(
    *, solved: bool, day: date = TODAY, daily: bool = False, level: str = "normal", hints: int = 0
) -> GameRecord:
    case = library()["ashford_manor"]
    p = clue_engine.new_progress(case, level)
    p.phase = "ended"
    p.hints = ["h"] * hints
    p.daily_date = day.isoformat() if daily else None
    suspect = case.culprit if solved else "s4"
    p.score = scoring.score(case, p, Accusation(suspect_id=suspect, motive_id="inheritance"))
    at = datetime(day.year, day.month, day.day, 12, tzinfo=UTC)
    return GameRecord(case, p, created_at=at - timedelta(minutes=10), updated_at=at)


def test_title_ladder():
    assert [career.title_for(n) for n in (0, 1, 2, 3, 6, 10, 20, 35, 99)] == [
        "Constable",
        "Detective Constable",
        "Detective Constable",
        "Detective Sergeant",
        "Detective Inspector",
        "Detective Chief Inspector",
        "Detective Superintendent",
        "Commissioner",
        "Commissioner",
    ]
    assert career.next_title(2) == ("Detective Sergeant", 1)
    assert career.next_title(35) is None


def test_promotion_only_when_crossing_a_rung():
    assert career.promotion(0, solved_now=True) == "Detective Constable"
    assert career.promotion(1, solved_now=True) is None
    assert career.promotion(2, solved_now=True) == "Detective Sergeant"
    assert career.promotion(2, solved_now=False) is None


def test_streaks_and_totals():
    days = [TODAY - timedelta(days=n) for n in range(6, -1, -1)]  # oldest first
    records = [
        closed(solved=True, day=days[0]),
        closed(solved=False, day=days[1], level="hard"),
        closed(solved=True, day=days[2], daily=True),
        closed(solved=True, day=days[4], daily=True, hints=2),  # day 3 missed: daily streak restarts
        closed(solved=True, day=days[5], daily=True),
        closed(solved=True, day=days[6], daily=True, level="easy"),
    ]
    summary = career.summarize(records, TODAY)
    assert (summary["closed"], summary["solved"], summary["title"]) == (6, 5, "Detective Sergeant")
    assert summary["next"] == {"title": "Detective Inspector", "solvesNeeded": 1}
    assert summary["streak"] == {"current": 4, "best": 4}
    assert summary["dailyStreak"] == {"current": 3, "best": 3, "playedToday": True}
    assert summary["hintsUsed"] == 2
    assert summary["byDifficulty"]["hard"] == {"closed": 1, "solved": 0}
    assert summary["bestRank"] == "Chief Inspector"  # 85: culprit + motive + spare turns, no evidence cited
    assert summary["casebook"][0]["closedOn"] == TODAY.isoformat()  # newest first


def test_daily_streak_survives_until_today_is_missed():
    yesterday = TODAY - timedelta(days=1)
    records = [
        closed(solved=True, day=yesterday - timedelta(days=1), daily=True),
        closed(solved=True, day=yesterday, daily=True),
    ]
    assert career.summarize(records, TODAY)["dailyStreak"]["current"] == 2  # today not played yet: still alive
    assert career.summarize(records, TODAY + timedelta(days=1))["dailyStreak"]["current"] == 0  # a day missed


def test_empty_career():
    summary = career.summarize([], TODAY)
    assert summary["title"] == "Constable" and summary["solveRate"] is None and summary["casebook"] == []


async def test_first_solve_shows_a_promotion_on_the_verdict():
    game = GameMaster(ScriptedLLM(), InMemoryRepo())
    case = library()["ashford_manor"]
    accusation = {"suspectId": case.culprit, "motiveId": "inheritance", "evidence": []}
    for thread, expected in (("t-1", "Detective Constable"), ("t-2", None)):
        await run(game, "ada", thread, {"type": "start", "caseId": "ashford_manor"})
        await run(game, "ada", thread, {"type": "accuse", "accusation": accusation})
        state = snapshot(await run(game, "ada", thread, {"type": "start"}))
        assert state["verdict"]["promotion"] == expected
