import uuid
from datetime import date, timedelta

from ag_ui.core import RunAgentInput

from app import daily
from app.engine.case_library import DAILY_CASE_ID, daily_case, library
from app.game import DAILY_TAKEN, GameMaster
from app.llm import ScriptedLLM
from app.store.repo import InMemoryRepo

DAY = date(2026, 10, 23)


def test_rotation_is_deterministic_and_never_repeats_within_a_cycle():
    n = len(library())
    assert daily_case(DAY).case_id == daily_case(DAY).case_id
    start = date.fromordinal((DAY.toordinal() // n) * n)  # first day of DAY's cycle
    cycle = [daily_case(start + timedelta(days=i)).case_id for i in range(n)]
    assert sorted(cycle) == sorted(library())


async def run(game: GameMaster, owner: str, thread: str, action: dict) -> list:
    run_input = RunAgentInput(
        thread_id=thread,
        run_id=uuid.uuid4().hex,
        state={},
        messages=[],
        tools=[],
        context=[],
        forwarded_props={"gameAction": action},
    )
    return [e async for e in game.run(run_input, owner)]


def snapshot(events: list) -> dict:
    return next(e.snapshot for e in events if e.type == "STATE_SNAPSHOT")


def errors(events: list) -> list[str]:
    return [e.message for e in events if e.type in ("RUN_ERROR",)] + [
        e.delta for e in events if e.type == "TEXT_MESSAGE_CONTENT"
    ]


def daily_game() -> GameMaster:
    game = GameMaster(ScriptedLLM(), InMemoryRepo())
    game.today = lambda: DAY
    return game


async def solve_daily(game: GameMaster, owner: str, thread: str) -> None:
    case = daily_case(DAY)
    await run(game, owner, thread, {"type": "start", "caseId": DAILY_CASE_ID})
    accusation = {"suspectId": case.culprit, "motiveId": case.solution.acceptable_motives[0], "evidence": []}
    await run(game, owner, thread, {"type": "accuse", "accusation": accusation})


async def test_everyone_gets_the_same_case_and_it_is_marked_daily():
    game = daily_game()
    a = snapshot(await run(game, "alice", "t-a", {"type": "start", "caseId": DAILY_CASE_ID}))
    b = snapshot(await run(game, "bob", "t-b", {"type": "start", "caseId": DAILY_CASE_ID}))
    assert a["caseId"] == b["caseId"] == daily_case(DAY).case_id
    assert a["daily"] == {"date": DAY.isoformat(), "leaderboardName": None}


async def test_one_attempt_per_player_but_the_same_thread_resumes():
    game = daily_game()
    await run(game, "alice", "t-1", {"type": "start", "caseId": DAILY_CASE_ID})
    second = await run(game, "alice", "t-2", {"type": "start", "caseId": DAILY_CASE_ID})
    assert DAILY_TAKEN in errors(second)
    resumed = await run(game, "alice", "t-1", {"type": "start"})
    assert snapshot(resumed)["daily"]["date"] == DAY.isoformat()


async def test_names_go_on_the_board_only_after_the_verdict():
    game = daily_game()
    await run(game, "alice", "t-1", {"type": "start", "caseId": DAILY_CASE_ID})
    early = await run(game, "alice", "t-1", {"type": "set_name", "name": "Alice"})
    assert any("once today's case is closed" in m for m in errors(early))

    accusation = {"suspectId": daily_case(DAY).culprit, "motiveId": "x", "evidence": []}
    accusation["motiveId"] = daily_case(DAY).solution.acceptable_motives[0]
    await run(game, "alice", "t-1", {"type": "accuse", "accusation": accusation})
    for bad in ("x", "Inspector <script>", "sex pest"):
        rejected = await run(game, "alice", "t-1", {"type": "set_name", "name": bad})
        assert any("name" in m.lower() for m in errors(rejected)), bad
    await run(game, "alice", "t-1", {"type": "set_name", "name": "  Inspector   Alice "})
    [mine] = await game.repo.daily_games(DAY.isoformat(), owner="alice")
    assert mine.record.progress.leaderboard_name == "Inspector Alice"


async def test_leaderboard_orders_by_score_then_turns_and_hides_owners():
    game = daily_game()
    for owner in ("alice", "bob", "carol"):
        await solve_daily(game, owner, f"t-{owner}")
    # Carol accused wrongly: lowest score, last place.
    case = daily_case(DAY)
    wrong = next(s.id for s in case.suspects if s.id != case.culprit)
    await run(game, "dave", "t-dave", {"type": "start", "caseId": DAILY_CASE_ID})
    await run(
        game,
        "dave",
        "t-dave",
        {"type": "accuse", "accusation": {"suspectId": wrong, "motiveId": case.motive_options[0].id, "evidence": []}},
    )
    await run(game, "alice", "t-alice", {"type": "set_name", "name": "Alice"})

    board = daily.leaderboard(await game.repo.daily_games(DAY.isoformat()))
    assert [e.rank for e in board] == [1, 2, 3, 4]
    assert board[-1].owner == "dave" and board[-1].score < board[0].score
    assert "Alice" in [e.name for e in board] and daily.ANONYMOUS in [e.name for e in board]
    assert set(board[0].public()) == {"rank", "name", "score", "turns", "minutes"}  # no owner or thread id
